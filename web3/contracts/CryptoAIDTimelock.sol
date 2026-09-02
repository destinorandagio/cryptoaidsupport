// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;
import {TimelockController} from "@openzeppelin/contracts/governance/TimelockController.sol";
contract CryptoAIDTimelock is TimelockController{constructor(uint256 minDelay,address[] memory proposers,address[] memory executors,address admin)TimelockController(minDelay,proposers,executors,admin){require(minDelay>=1 days,"DELAY_LOW");}}
