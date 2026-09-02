// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;
import {VestingWallet} from "@openzeppelin/contracts/finance/VestingWallet.sol";
contract CryptoAIDVestingFactory{event VestingCreated(address indexed beneficiary,address indexed wallet,uint64 start,uint64 duration);function create(address beneficiary,uint64 start,uint64 duration)external returns(address wallet){require(beneficiary!=address(0)&&duration>0,"BAD");VestingWallet v=new VestingWallet(beneficiary,start,duration);wallet=address(v);emit VestingCreated(beneficiary,wallet,start,duration);} }
