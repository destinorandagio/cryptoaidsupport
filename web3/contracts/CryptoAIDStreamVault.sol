// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {IERC20} from "@openzeppelin/contracts/token/ERC20/IERC20.sol";
import {SafeERC20} from "@openzeppelin/contracts/token/ERC20/utils/SafeERC20.sol";
import {ReentrancyGuard} from "@openzeppelin/contracts/utils/ReentrancyGuard.sol";

/// @notice Linear token streams for DUX/DRX rewards, grants, contributors and campaigns.
contract CryptoAIDStreamVault is ReentrancyGuard {
    using SafeERC20 for IERC20;

    struct Stream { address sender; address recipient; address token; uint64 start; uint64 end; uint128 amount; uint128 claimed; bool cancelled; }
    uint256 public nextStreamId = 1;
    mapping(uint256 => Stream) public streams;

    event StreamCreated(uint256 indexed id,address indexed sender,address indexed recipient,address token,uint256 amount,uint64 start,uint64 end);
    event Claimed(uint256 indexed id,address indexed recipient,uint256 amount);
    event Cancelled(uint256 indexed id,uint256 recipientAmount,uint256 senderRefund);

    function createStream(address recipient,address token,uint128 amount,uint64 start,uint64 end) external nonReentrant returns(uint256 id){
        require(recipient!=address(0)&&token!=address(0),"ZERO_ADDRESS");
        require(amount>0&&end>start&&end>block.timestamp,"BAD_STREAM");
        id=nextStreamId++;
        streams[id]=Stream(msg.sender,recipient,token,start,end,amount,0,false);
        IERC20(token).safeTransferFrom(msg.sender,address(this),amount);
        emit StreamCreated(id,msg.sender,recipient,token,amount,start,end);
    }

    function vested(uint256 id) public view returns(uint256){
        Stream memory s=streams[id];
        if(s.sender==address(0)) return 0;
        uint256 t=s.cancelled ? block.timestamp : block.timestamp;
        if(t<=s.start) return 0;
        if(t>=s.end) return s.amount;
        return uint256(s.amount)*(t-s.start)/(s.end-s.start);
    }

    function claim(uint256 id) external nonReentrant {
        Stream storage s=streams[id]; require(msg.sender==s.recipient,"NOT_RECIPIENT"); require(!s.cancelled,"CANCELLED");
        uint256 v=vested(id); uint256 due=v-s.claimed; require(due>0,"NOTHING"); s.claimed+=uint128(due);
        IERC20(s.token).safeTransfer(s.recipient,due); emit Claimed(id,s.recipient,due);
    }

    function cancel(uint256 id) external nonReentrant {
        Stream storage s=streams[id]; require(msg.sender==s.sender,"NOT_SENDER"); require(!s.cancelled,"CANCELLED");
        uint256 v=vested(id); uint256 due=v-s.claimed; uint256 refund=uint256(s.amount)-v; s.cancelled=true; s.claimed+=uint128(due);
        if(due>0) IERC20(s.token).safeTransfer(s.recipient,due); if(refund>0) IERC20(s.token).safeTransfer(s.sender,refund);
        emit Cancelled(id,due,refund);
    }
}
