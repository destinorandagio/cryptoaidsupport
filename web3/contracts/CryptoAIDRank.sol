// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {ERC721} from "@openzeppelin/contracts/token/ERC721/ERC721.sol";
import {Ownable} from "@openzeppelin/contracts/access/Ownable.sol";

/// @notice One evolving CryptoAID reputation NFT per wallet. Non-transferable by design.
contract CryptoAIDRank is ERC721, Ownable {
    struct Profile { uint64 xp; uint32 missions; uint16 rank; uint64 updatedAt; }
    mapping(address => uint256) public tokenOf;
    mapping(uint256 => Profile) public profile;
    mapping(address => bool) public operators;
    uint256 public nextId = 1;

    event OperatorSet(address indexed operator, bool allowed);
    event RankMinted(address indexed user, uint256 indexed tokenId);
    event Progress(address indexed user, uint256 indexed tokenId, uint256 xpAdded, uint256 totalXp, uint256 rank);

    modifier onlyOperator() { require(operators[msg.sender] || msg.sender == owner(), "NOT_OPERATOR"); _; }

    constructor(address initialOwner) ERC721("CryptoAID Rank", "CAIDR") Ownable(initialOwner) {}

    function setOperator(address op, bool allowed) external onlyOwner { operators[op] = allowed; emit OperatorSet(op, allowed); }

    function mint() external returns (uint256 id) {
        require(tokenOf[msg.sender] == 0, "ALREADY_MINTED");
        id = nextId++;
        tokenOf[msg.sender] = id;
        profile[id] = Profile(0, 0, 1, uint64(block.timestamp));
        _safeMint(msg.sender, id);
        emit RankMinted(msg.sender, id);
    }

    function addProgress(address user, uint64 xpAdded, uint32 missionAdded) external onlyOperator {
        uint256 id = tokenOf[user]; require(id != 0, "NO_RANK_NFT");
        Profile storage p = profile[id];
        p.xp += xpAdded; p.missions += missionAdded; p.updatedAt = uint64(block.timestamp);
        p.rank = _rankFor(p.xp);
        emit Progress(user, id, xpAdded, p.xp, p.rank);
    }

    function _rankFor(uint256 xp) internal pure returns (uint16) {
        if (xp >= 100_000) return 6; // Legend
        if (xp >= 50_000) return 5;  // Validator
        if (xp >= 20_000) return 4;  // Sentinel
        if (xp >= 7_500) return 3;   // Guardian
        if (xp >= 2_000) return 2;   // Scout
        return 1;                    // Genesis
    }

    function rankMultiplierBps(address user) external view returns (uint256) {
        uint256 id = tokenOf[user]; if (id == 0) return 10_000;
        uint16 r = profile[id].rank;
        return r == 6 ? 15_000 : r == 5 ? 13_500 : r == 4 ? 12_000 : r == 3 ? 11_000 : r == 2 ? 10_500 : 10_000;
    }

    function transferFrom(address, address, uint256) public pure override { revert("SOULBOUND"); }
    function safeTransferFrom(address, address, uint256, bytes memory) public pure override { revert("SOULBOUND"); }
}
