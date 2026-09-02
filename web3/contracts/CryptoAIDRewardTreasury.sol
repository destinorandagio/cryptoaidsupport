// SPDX-License-Identifier: MIT
pragma solidity ^0.8.26;
import {IERC20} from "@openzeppelin/contracts/token/ERC20/IERC20.sol";
import {SafeERC20} from "@openzeppelin/contracts/token/ERC20/utils/SafeERC20.sol";
import {AccessControl} from "@openzeppelin/contracts/access/AccessControl.sol";
import {Pausable} from "@openzeppelin/contracts/utils/Pausable.sol";
import {ReentrancyGuard} from "@openzeppelin/contracts/utils/ReentrancyGuard.sol";
contract CryptoAIDRewardTreasury is AccessControl,Pausable,ReentrancyGuard {
    using SafeERC20 for IERC20;
    bytes32 public constant SPENDER_ROLE=keccak256("SPENDER_ROLE");
    bytes32 public constant GUARDIAN_ROLE=keccak256("GUARDIAN_ROLE");
    IERC20 public immutable USDT;
    mapping(address=>uint256) public tokenDailyCap;
    mapping(address=>mapping(uint256=>uint256)) public tokenSpent;
    mapping(bytes32=>bool) public payoutUsed;
    event Paid(address indexed asset,address indexed to,uint256 amount,bytes32 indexed payoutId);
    event CapSet(address indexed token,uint256 dailyCap);
    constructor(address admin,address guardian,address usdt){require(admin!=address(0)&&guardian!=address(0)&&usdt!=address(0)&&usdt.code.length>0,"BAD_INIT");USDT=IERC20(usdt);_grantRole(DEFAULT_ADMIN_ROLE,admin);_grantRole(GUARDIAN_ROLE,guardian);}
    function dayIndex() public view returns(uint256){return block.timestamp/1 days;}
    function setCap(address token,uint256 cap) external onlyRole(DEFAULT_ADMIN_ROLE){require(token!=address(0)&&token.code.length>0&&cap>0,"BAD_CAP");tokenDailyCap[token]=cap;emit CapSet(token,cap);}
    function payToken(IERC20 token,address to,uint256 amount,bytes32 payoutId) external onlyRole(SPENDER_ROLE) whenNotPaused nonReentrant {require(address(token)!=address(0)&&address(token).code.length>0&&to!=address(0)&&to!=address(this)&&amount>0,"BAD");require(payoutId!=bytes32(0)&&!payoutUsed[payoutId],"REPLAY");uint256 d=dayIndex();uint256 cap=tokenDailyCap[address(token)];require(cap>0&&tokenSpent[address(token)][d]+amount<=cap,"CAP");require(token.balanceOf(address(this))>=amount,"INSOLVENT");payoutUsed[payoutId]=true;tokenSpent[address(token)][d]+=amount;token.safeTransfer(to,amount);emit Paid(address(token),to,amount,payoutId);}
    function payUSDT(address to,uint256 amount,bytes32 payoutId) external onlyRole(SPENDER_ROLE) whenNotPaused nonReentrant {require(to!=address(0)&&to!=address(this)&&amount>0,"BAD");require(payoutId!=bytes32(0)&&!payoutUsed[payoutId],"REPLAY");uint256 d=dayIndex();uint256 cap=tokenDailyCap[address(USDT)];require(cap>0&&tokenSpent[address(USDT)][d]+amount<=cap,"CAP");require(USDT.balanceOf(address(this))>=amount,"INSOLVENT");payoutUsed[payoutId]=true;tokenSpent[address(USDT)][d]+=amount;USDT.safeTransfer(to,amount);emit Paid(address(USDT),to,amount,payoutId);}
    function pause() external onlyRole(GUARDIAN_ROLE){_pause();}
    function unpause() external onlyRole(DEFAULT_ADMIN_ROLE){_unpause();}
}
