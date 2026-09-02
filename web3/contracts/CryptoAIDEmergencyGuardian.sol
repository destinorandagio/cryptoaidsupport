// SPDX-License-Identifier: MIT
pragma solidity ^0.8.26;

import {ReentrancyGuard} from "@openzeppelin/contracts/utils/ReentrancyGuard.sol";

interface ICryptoAIDPausableTarget { function pause() external; }

contract CryptoAIDEmergencyGuardian is ReentrancyGuard {
    address[3] public guardians;
    mapping(bytes32 => uint8) public approvals;
    mapping(bytes32 => mapping(address => bool)) public approvedBy;
    event Approved(bytes32 indexed action,address indexed guardian,address indexed target);
    event PauseExecuted(bytes32 indexed action,address indexed target);

    constructor(address[3] memory g) {
        require(g[0]!=address(0)&&g[1]!=address(0)&&g[2]!=address(0),"ZERO");
        require(g[0]!=g[1]&&g[0]!=g[2]&&g[1]!=g[2],"DUP_GUARDIAN");
        guardians=g;
    }
    modifier onlyGuardian(){require(msg.sender==guardians[0]||msg.sender==guardians[1]||msg.sender==guardians[2],"GUARDIAN");_;}
    function approvePause(address target) external onlyGuardian nonReentrant {
        require(target!=address(0)&&target.code.length>0,"BAD_TARGET");
        bytes32 action=keccak256(abi.encode(block.chainid,address(this),target,"PAUSE"));
        require(!approvedBy[action][msg.sender],"DUP");
        approvedBy[action][msg.sender]=true;
        uint8 count=approvals[action]+1;
        approvals[action]=count;
        emit Approved(action,msg.sender,target);
        if(count>=2){
            approvals[action]=0;
            ICryptoAIDPausableTarget(target).pause();
            emit PauseExecuted(action,target);
        }
    }
}
