// SPDX-License-Identifier: MIT
pragma solidity ^0.8.26;
import {AccessControl} from "@openzeppelin/contracts/access/AccessControl.sol";
import {ReentrancyGuard} from "@openzeppelin/contracts/utils/ReentrancyGuard.sol";
contract CryptoAIDPOLRewardRouter is AccessControl,ReentrancyGuard{
    bytes32 public constant DISTRIBUTOR_ROLE=keccak256("DISTRIBUTOR_ROLE");
    uint256 public maxSinglePayout; uint256 public dailyCap;
    mapping(uint256=>uint256) public spentByDay; mapping(bytes32=>bool) public payoutUsed;
    event Funded(address indexed from,uint256 amount); event Paid(address indexed to,uint256 amount,bytes32 indexed payoutId); event LimitsSet(uint256 maxSingle,uint256 daily);
    constructor(address admin,uint256 cap){require(admin!=address(0)&&cap>0,"BAD");_grantRole(DEFAULT_ADMIN_ROLE,admin);_grantRole(DISTRIBUTOR_ROLE,admin);maxSinglePayout=cap;dailyCap=cap*10;}
    receive()external payable{require(msg.value>0,"ZERO");emit Funded(msg.sender,msg.value);}
    function setLimits(uint256 single,uint256 daily)external onlyRole(DEFAULT_ADMIN_ROLE){require(single>0&&daily>=single,"BAD_LIMIT");maxSinglePayout=single;dailyCap=daily;emit LimitsSet(single,daily);}
    function payout(address payable to,uint256 amount,bytes32 payoutId)external onlyRole(DISTRIBUTOR_ROLE) nonReentrant{
        require(to!=address(0)&&to!=address(this)&&amount>0&&amount<=maxSinglePayout,"BAD");require(payoutId!=bytes32(0)&&!payoutUsed[payoutId],"REPLAY");
        uint256 day=block.timestamp/1 days;require(spentByDay[day]+amount<=dailyCap,"DAILY_CAP");require(address(this).balance>=amount,"INSOLVENT");
        payoutUsed[payoutId]=true;spentByDay[day]+=amount;(bool ok,)=to.call{value:amount}("");require(ok,"FAIL");emit Paid(to,amount,payoutId);
    }
}
