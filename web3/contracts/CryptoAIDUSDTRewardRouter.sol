// SPDX-License-Identifier: MIT
pragma solidity ^0.8.26;
import {IERC20} from "@openzeppelin/contracts/token/ERC20/IERC20.sol";
import {SafeERC20} from "@openzeppelin/contracts/token/ERC20/utils/SafeERC20.sol";
import {AccessControl} from "@openzeppelin/contracts/access/AccessControl.sol";
import {Pausable} from "@openzeppelin/contracts/utils/Pausable.sol";
import {ReentrancyGuard} from "@openzeppelin/contracts/utils/ReentrancyGuard.sol";
contract CryptoAIDUSDTRewardRouter is AccessControl,Pausable,ReentrancyGuard {
 using SafeERC20 for IERC20;
 bytes32 public constant DISTRIBUTOR_ROLE=keccak256("DISTRIBUTOR_ROLE");
 bytes32 public constant GUARDIAN_ROLE=keccak256("GUARDIAN_ROLE");
 IERC20 public immutable USDT; uint256 public maxSinglePayout; uint256 public dailyCap; uint256 public totalPaid;
 mapping(uint256=>uint256) public spentByDay; mapping(bytes32=>bool) public payoutUsed;
 event Paid(address indexed to,uint256 amount,bytes32 indexed payoutId); event LimitsSet(uint256 maxSingle,uint256 daily);
 constructor(address admin,address guardian,address usdt,uint256 single,uint256 daily){require(admin!=address(0)&&guardian!=address(0)&&usdt!=address(0)&&usdt.code.length>0&&single>0&&daily>=single,"BAD_INIT");USDT=IERC20(usdt);maxSinglePayout=single;dailyCap=daily;_grantRole(DEFAULT_ADMIN_ROLE,admin);_grantRole(DISTRIBUTOR_ROLE,admin);_grantRole(GUARDIAN_ROLE,guardian);}
 function setLimits(uint256 single,uint256 daily) external onlyRole(DEFAULT_ADMIN_ROLE){require(single>0&&daily>=single,"BAD_LIMIT");maxSinglePayout=single;dailyCap=daily;emit LimitsSet(single,daily);}
 function payout(address to,uint256 amount,bytes32 payoutId) external onlyRole(DISTRIBUTOR_ROLE) whenNotPaused nonReentrant {require(to!=address(0)&&to!=address(this)&&amount>0&&amount<=maxSinglePayout,"BAD");require(payoutId!=bytes32(0)&&!payoutUsed[payoutId],"REPLAY");uint256 day=block.timestamp/1 days;require(spentByDay[day]+amount<=dailyCap,"DAILY_CAP");require(USDT.balanceOf(address(this))>=amount,"INSOLVENT");payoutUsed[payoutId]=true;spentByDay[day]+=amount;totalPaid+=amount;USDT.safeTransfer(to,amount);emit Paid(to,amount,payoutId);}
 function pause() external onlyRole(GUARDIAN_ROLE){_pause();} function unpause() external onlyRole(DEFAULT_ADMIN_ROLE){_unpause();}
}
