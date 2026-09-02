// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {IERC20} from "@openzeppelin/contracts/token/ERC20/IERC20.sol";
import {SafeERC20} from "@openzeppelin/contracts/token/ERC20/utils/SafeERC20.sol";
import {Ownable} from "@openzeppelin/contracts/access/Ownable.sol";
import {ReentrancyGuard} from "@openzeppelin/contracts/utils/ReentrancyGuard.sol";

/// @notice Generic funded ERC20 staking pool using reward-per-token accounting; no depositor funds pay prior rewards.
contract CryptoAIDStaking is Ownable, ReentrancyGuard {
    using SafeERC20 for IERC20;
    IERC20 public immutable stakingToken;
    IERC20 public immutable rewardToken;
    uint256 public duration = 30 days;
    uint256 public periodFinish;
    uint256 public rewardRate;
    uint256 public lastUpdateTime;
    uint256 public rewardPerTokenStored;
    uint256 public totalSupply;
    mapping(address => uint256) public balanceOf;
    mapping(address => uint256) public userRewardPerTokenPaid;
    mapping(address => uint256) public rewards;

    constructor(address initialOwner, IERC20 stakeToken, IERC20 reward) Ownable(initialOwner) { stakingToken = stakeToken; rewardToken = reward; }
    modifier updateReward(address a) { rewardPerTokenStored = rewardPerToken(); lastUpdateTime = lastTimeRewardApplicable(); if (a != address(0)) { rewards[a] = earned(a); userRewardPerTokenPaid[a] = rewardPerTokenStored; } _; }
    function lastTimeRewardApplicable() public view returns(uint256){ return block.timestamp < periodFinish ? block.timestamp : periodFinish; }
    function rewardPerToken() public view returns(uint256){ if(totalSupply==0) return rewardPerTokenStored; return rewardPerTokenStored + (lastTimeRewardApplicable()-lastUpdateTime)*rewardRate*1e18/totalSupply; }
    function earned(address a) public view returns(uint256){ return balanceOf[a]*(rewardPerToken()-userRewardPerTokenPaid[a])/1e18 + rewards[a]; }
    function stake(uint256 amount) external nonReentrant updateReward(msg.sender) { require(amount>0,"ZERO"); totalSupply+=amount; balanceOf[msg.sender]+=amount; stakingToken.safeTransferFrom(msg.sender,address(this),amount); }
    function withdraw(uint256 amount) public nonReentrant updateReward(msg.sender) { require(amount>0 && balanceOf[msg.sender]>=amount,"BAD_AMOUNT"); totalSupply-=amount; balanceOf[msg.sender]-=amount; stakingToken.safeTransfer(msg.sender,amount); }
    function claim() public nonReentrant updateReward(msg.sender) { uint256 r=rewards[msg.sender]; if(r>0){ rewards[msg.sender]=0; rewardToken.safeTransfer(msg.sender,r); } }
    function exit() external { uint256 b=balanceOf[msg.sender]; if(b>0) withdraw(b); claim(); }
    function notifyRewardAmount(uint256 reward) external onlyOwner updateReward(address(0)) { require(block.timestamp>=periodFinish,"ACTIVE_PERIOD"); require(reward>0,"ZERO"); rewardToken.safeTransferFrom(msg.sender,address(this),reward); rewardRate=reward/duration; require(rewardRate>0,"RATE_ZERO"); lastUpdateTime=block.timestamp; periodFinish=block.timestamp+duration; }
    function setDuration(uint256 newDuration) external onlyOwner { require(block.timestamp>=periodFinish,"ACTIVE_PERIOD"); require(newDuration>=1 days,"TOO_SHORT"); duration=newDuration; }
}
