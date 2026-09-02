// SPDX-License-Identifier: MIT
pragma solidity ^0.8.26;
import {IERC20} from "@openzeppelin/contracts/token/ERC20/IERC20.sol";
import {SafeERC20} from "@openzeppelin/contracts/token/ERC20/utils/SafeERC20.sol";
import {AccessControl} from "@openzeppelin/contracts/access/AccessControl.sol";
import {Pausable} from "@openzeppelin/contracts/utils/Pausable.sol";
import {ReentrancyGuard} from "@openzeppelin/contracts/utils/ReentrancyGuard.sol";
contract CryptoAIDCasePayment is AccessControl,Pausable,ReentrancyGuard {
 using SafeERC20 for IERC20;
 bytes32 public constant PAYMENT_AUTHORITY_ROLE=keccak256("PAYMENT_AUTHORITY_ROLE"); bytes32 public constant GUARDIAN_ROLE=keccak256("GUARDIAN_ROLE");
 enum Purpose{NONE,ONBOARDING,FIRST_CASE,SUBSEQUENT_CASE}
 struct Intent{bytes32 sicIdRef;bytes32 caseId;bytes32 idempotencyKey;address payer;uint256 amount;Purpose purpose;bool settled;}
 IERC20 public immutable USDT; address public immutable TREASURY; uint8 public immutable USDT_DECIMALS;
 mapping(bytes32=>Intent) public intents; mapping(bytes32=>bool) public idempotencyUsed;
 event IntentCreated(bytes32 indexed paymentIntentId,bytes32 indexed sicIdRef,bytes32 indexed caseId,address payer,uint256 amount,Purpose purpose,bytes32 idempotencyKey);
 event Settled(bytes32 indexed paymentIntentId,bytes32 indexed sicIdRef,bytes32 indexed caseId,address payer,address treasury,uint256 amount,Purpose purpose,bytes32 idempotencyKey);
 constructor(address admin,address guardian,address usdt,address treasury,uint8 usdtDecimals){require(admin!=address(0)&&guardian!=address(0)&&usdt!=address(0)&&treasury!=address(0)&&usdt.code.length>0,"BAD_INIT");require(usdtDecimals>0&&usdtDecimals<=18,"BAD_DECIMALS");USDT=IERC20(usdt);TREASURY=treasury;USDT_DECIMALS=usdtDecimals;_grantRole(DEFAULT_ADMIN_ROLE,admin);_grantRole(PAYMENT_AUTHORITY_ROLE,admin);_grantRole(GUARDIAN_ROLE,guardian);}
 function units(uint256 whole) public view returns(uint256){return whole*(10**uint256(USDT_DECIMALS));}
 function expectedAmount(Purpose purpose) public view returns(uint256){if(purpose==Purpose.ONBOARDING)return units(100);if(purpose==Purpose.FIRST_CASE)return units(400);if(purpose==Purpose.SUBSEQUENT_CASE)return units(500);revert("BAD_PURPOSE");}
 function createIntent(bytes32 paymentIntentId,bytes32 sicIdRef,bytes32 caseId,bytes32 idempotencyKey,address payer,Purpose purpose) external onlyRole(PAYMENT_AUTHORITY_ROLE) whenNotPaused {require(paymentIntentId!=bytes32(0)&&sicIdRef!=bytes32(0)&&idempotencyKey!=bytes32(0)&&payer!=address(0),"BAD_INPUT");require(intents[paymentIntentId].payer==address(0)&&!idempotencyUsed[idempotencyKey],"DUPLICATE");if(purpose!=Purpose.ONBOARDING)require(caseId!=bytes32(0),"CASE_REQUIRED");uint256 amount=expectedAmount(purpose);idempotencyUsed[idempotencyKey]=true;intents[paymentIntentId]=Intent(sicIdRef,caseId,idempotencyKey,payer,amount,purpose,false);emit IntentCreated(paymentIntentId,sicIdRef,caseId,payer,amount,purpose,idempotencyKey);}
 function settle(bytes32 paymentIntentId) external whenNotPaused nonReentrant {Intent storage x=intents[paymentIntentId];require(x.payer!=address(0)&&!x.settled,"INVALID_INTENT");require(msg.sender==x.payer,"WRONG_PAYER");x.settled=true;uint256 beforeBal=USDT.balanceOf(TREASURY);USDT.safeTransferFrom(msg.sender,TREASURY,x.amount);uint256 afterBal=USDT.balanceOf(TREASURY);require(afterBal>=beforeBal&&afterBal-beforeBal==x.amount,"NON_STANDARD_USDT");emit Settled(paymentIntentId,x.sicIdRef,x.caseId,msg.sender,TREASURY,x.amount,x.purpose,x.idempotencyKey);}
 function pause() external onlyRole(GUARDIAN_ROLE){_pause();} function unpause() external onlyRole(DEFAULT_ADMIN_ROLE){_unpause();}
}
