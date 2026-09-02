// SPDX-License-Identifier: MIT
pragma solidity ^0.8.26;

import {IERC20} from "@openzeppelin/contracts/token/ERC20/IERC20.sol";
import {SafeERC20} from "@openzeppelin/contracts/token/ERC20/utils/SafeERC20.sol";
import {Ownable} from "@openzeppelin/contracts/access/Ownable.sol";
import {Pausable} from "@openzeppelin/contracts/utils/Pausable.sol";
import {ReentrancyGuard} from "@openzeppelin/contracts/utils/ReentrancyGuard.sol";

interface IRank {
    function addProgress(address user, uint64 xpAdded, uint32 missionAdded) external;
    function rankMultiplierBps(address user) external view returns (uint256);
}

contract CryptoAIDUsefulMiner is Ownable, Pausable, ReentrancyGuard {
    using SafeERC20 for IERC20;
    struct Mission { uint64 xp; uint128 polReward; uint128 duxReward; uint128 drxReward; bool active; }
    IERC20 public immutable DUX;
    IERC20 public immutable DRX;
    IRank public immutable rank;
    mapping(bytes32 => Mission) public missions;
    mapping(bytes32 => bool) public consumedProof;
    mapping(address => bool) public verifiers;

    event MissionSet(bytes32 indexed missionId, uint64 xp, uint256 polReward, uint256 duxReward, uint256 drxReward, bool active);
    event WorkMined(address indexed user, bytes32 indexed missionId, bytes32 indexed proofId, uint256 pol, uint256 dux, uint256 drx, uint256 xp);
    event VerifierSet(address indexed verifier, bool allowed);
    event EmergencyPOLWithdrawn(address indexed to,uint256 amount);
    event EmergencyTokenWithdrawn(address indexed token,address indexed to,uint256 amount);

    modifier onlyVerifier() { require(verifiers[msg.sender] || msg.sender == owner(), "NOT_VERIFIER"); _; }

    constructor(address initialOwner, address dux, address drx, address rankAddress) Ownable(initialOwner) {
        require(initialOwner != address(0) && dux != address(0) && drx != address(0) && rankAddress != address(0), "ZERO_ADDRESS");
        require(dux != drx && dux.code.length > 0 && drx.code.length > 0 && rankAddress.code.length > 0, "BAD_CONTRACT");
        DUX = IERC20(dux); DRX = IERC20(drx); rank = IRank(rankAddress);
    }

    receive() external payable {}
    function setVerifier(address verifier, bool allowed) external onlyOwner { require(verifier != address(0),"ZERO_VERIFIER"); verifiers[verifier] = allowed; emit VerifierSet(verifier, allowed); }
    function setMission(bytes32 id, uint64 xp, uint128 polReward, uint128 duxReward, uint128 drxReward, bool active) external onlyOwner {
        require(id != bytes32(0),"ZERO_MISSION");
        missions[id] = Mission(xp, polReward, duxReward, drxReward, active);
        emit MissionSet(id, xp, polReward, duxReward, drxReward, active);
    }
    function mine(address user, bytes32 missionId, bytes32 proofId) external onlyVerifier whenNotPaused nonReentrant {
        require(user != address(0) && proofId != bytes32(0), "BAD_INPUT"); require(!consumedProof[proofId], "PROOF_USED");
        Mission memory m = missions[missionId]; require(m.active, "MISSION_INACTIVE");
        consumedProof[proofId] = true;
        uint256 boost = rank.rankMultiplierBps(user); require(boost >= 10_000 && boost <= 20_000,"BAD_BOOST");
        uint256 pol = uint256(m.polReward) * boost / 10_000;
        uint256 dux = uint256(m.duxReward) * boost / 10_000;
        uint256 drx = uint256(m.drxReward) * boost / 10_000;
        require(address(this).balance >= pol, "POL_POOL_LOW");
        require(DUX.balanceOf(address(this)) >= dux, "DUX_POOL_LOW");
        require(DRX.balanceOf(address(this)) >= drx, "DRX_POOL_LOW");
        rank.addProgress(user, m.xp, 1);
        if (dux > 0) DUX.safeTransfer(user, dux);
        if (drx > 0) DRX.safeTransfer(user, drx);
        if (pol > 0) { (bool ok,) = payable(user).call{value: pol}(""); require(ok, "POL_TRANSFER_FAILED"); }
        emit WorkMined(user, missionId, proofId, pol, dux, drx, m.xp);
    }
    function pause() external onlyOwner { _pause(); }
    function unpause() external onlyOwner { _unpause(); }
    function emergencyWithdrawPOL(address payable to, uint256 amount) external onlyOwner nonReentrant { require(paused(), "PAUSE_FIRST"); require(to != address(0) && amount > 0 && address(this).balance >= amount,"BAD_WITHDRAW"); (bool ok,) = to.call{value: amount}(""); require(ok,"POL_FAIL"); emit EmergencyPOLWithdrawn(to,amount); }
    function emergencyWithdrawToken(IERC20 token, address to, uint256 amount) external onlyOwner nonReentrant { require(paused(), "PAUSE_FIRST"); require(address(token) != address(0) && address(token).code.length > 0 && to != address(0) && amount > 0 && token.balanceOf(address(this)) >= amount,"BAD_WITHDRAW"); token.safeTransfer(to, amount); emit EmergencyTokenWithdrawn(address(token),to,amount); }
}
