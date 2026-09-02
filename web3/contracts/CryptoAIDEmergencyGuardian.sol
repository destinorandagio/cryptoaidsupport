// SPDX-License-Identifier: MIT
pragma solidity ^0.8.26;

import {ReentrancyGuard} from "@openzeppelin/contracts/utils/ReentrancyGuard.sol";

interface ICryptoAIDPausableTarget { function pause() external; }

/// @notice Emergency pause authority controlled by the canonical CryptoAID treasury wallet.
/// @dev This intentionally replaces the former 2-of-3 guardian model per project authority decision.
contract CryptoAIDEmergencyGuardian is ReentrancyGuard {
    address public immutable guardian;

    event PauseExecuted(address indexed guardian, address indexed target);

    constructor(address guardian_) {
        require(guardian_ != address(0), "ZERO_GUARDIAN");
        guardian = guardian_;
    }

    modifier onlyGuardian() {
        require(msg.sender == guardian, "GUARDIAN");
        _;
    }

    function pauseTarget(address target) external onlyGuardian nonReentrant {
        require(target != address(0) && target.code.length > 0, "BAD_TARGET");
        ICryptoAIDPausableTarget(target).pause();
        emit PauseExecuted(msg.sender, target);
    }
}
