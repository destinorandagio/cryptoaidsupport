// SPDX-License-Identifier: MIT
pragma solidity ^0.8.26;
import {IERC20} from "@openzeppelin/contracts/token/ERC20/IERC20.sol";
import {SafeERC20} from "@openzeppelin/contracts/token/ERC20/utils/SafeERC20.sol";
import {ReentrancyGuard} from "@openzeppelin/contracts/utils/ReentrancyGuard.sol";
contract CryptoAIDBoostLock is ReentrancyGuard {
    using SafeERC20 for IERC20;
    IERC20 public immutable dux; IERC20 public immutable drx;
    struct Position { uint128 duxAmount; uint128 drxAmount; uint64 unlockAt; }
    mapping(address=>Position) public positions;
    event Locked(address indexed user,uint256 duxAmount,uint256 drxAmount,uint64 unlockAt);
    event Withdrawn(address indexed user,uint256 duxAmount,uint256 drxAmount);
    constructor(address _dux,address _drx){require(_dux!=address(0)&&_drx!=address(0)&&_dux!=_drx,"BAD_TOKEN");require(_dux.code.length>0&&_drx.code.length>0,"NOT_CONTRACT");dux=IERC20(_dux);drx=IERC20(_drx);}
    function lock(uint128 duxAmount,uint128 drxAmount,uint64 duration) external nonReentrant {
        require(duxAmount>0||drxAmount>0,"ZERO_AMOUNT"); require(duration>=1 days&&duration<=365 days,"BAD_DURATION");
        Position storage p=positions[msg.sender]; require(p.unlockAt<=block.timestamp,"ACTIVE_LOCK");
        if(duxAmount>0) dux.safeTransferFrom(msg.sender,address(this),duxAmount); if(drxAmount>0) drx.safeTransferFrom(msg.sender,address(this),drxAmount);
        p.duxAmount=duxAmount;p.drxAmount=drxAmount;p.unlockAt=uint64(block.timestamp+duration);emit Locked(msg.sender,duxAmount,drxAmount,p.unlockAt);
    }
    function boostBps(address user) public view returns(uint256){Position memory p=positions[user];if(p.unlockAt<=block.timestamp)return 10000;uint256 remaining=p.unlockAt-block.timestamp;uint256 timeBoost=remaining>=180 days?3000:(remaining*3000)/(180 days);uint256 dual=(p.duxAmount>0&&p.drxAmount>0)?1000:0;return 10000+timeBoost+dual;}
    function withdraw() external nonReentrant {Position memory p=positions[msg.sender];require(p.unlockAt!=0&&block.timestamp>=p.unlockAt,"LOCKED");delete positions[msg.sender];if(p.duxAmount>0)dux.safeTransfer(msg.sender,p.duxAmount);if(p.drxAmount>0)drx.safeTransfer(msg.sender,p.drxAmount);emit Withdrawn(msg.sender,p.duxAmount,p.drxAmount);}
}
