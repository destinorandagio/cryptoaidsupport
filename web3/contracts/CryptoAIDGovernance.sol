// SPDX-License-Identifier: MIT
pragma solidity ^0.8.26;

import {Governor} from "@openzeppelin/contracts/governance/Governor.sol";
import {GovernorSettings} from "@openzeppelin/contracts/governance/extensions/GovernorSettings.sol";
import {GovernorCountingSimple} from "@openzeppelin/contracts/governance/extensions/GovernorCountingSimple.sol";
import {GovernorVotes} from "@openzeppelin/contracts/governance/extensions/GovernorVotes.sol";
import {GovernorVotesQuorumFraction} from "@openzeppelin/contracts/governance/extensions/GovernorVotesQuorumFraction.sol";
import {GovernorTimelockControl} from "@openzeppelin/contracts/governance/extensions/GovernorTimelockControl.sol";
import {IVotes} from "@openzeppelin/contracts/governance/utils/IVotes.sol";
import {TimelockController} from "@openzeppelin/contracts/governance/TimelockController.sol";

contract CryptoAIDGovernance is Governor, GovernorSettings, GovernorCountingSimple, GovernorVotes, GovernorVotesQuorumFraction, GovernorTimelockControl {
    constructor(IVotes votesToken_, TimelockController timelock_)
        Governor("CryptoAID Governance")
        GovernorSettings(12 hours, 3 days + 12 hours, 0)
        GovernorVotes(votesToken_)
        GovernorVotesQuorumFraction(4)
        GovernorTimelockControl(timelock_)
    {
        require(address(votesToken_) != address(0) && address(votesToken_).code.length > 0, "BAD_VOTES_TOKEN");
        require(address(timelock_) != address(0) && address(timelock_).code.length > 0, "BAD_TIMELOCK");
    }

    function votingDelay() public view override(Governor, GovernorSettings) returns (uint256) { return super.votingDelay(); }
    function votingPeriod() public view override(Governor, GovernorSettings) returns (uint256) { return super.votingPeriod(); }
    function proposalThreshold() public view override(Governor, GovernorSettings) returns (uint256) { return super.proposalThreshold(); }
    function quorum(uint256 timepoint) public view override(Governor, GovernorVotesQuorumFraction) returns (uint256) { return super.quorum(timepoint); }
    function _quorumReached(uint256 proposalId) internal view override(Governor, GovernorCountingSimple) returns (bool) { return super._quorumReached(proposalId); }
    function _voteSucceeded(uint256 proposalId) internal view override(Governor, GovernorCountingSimple) returns (bool) { return super._voteSucceeded(proposalId); }
    function _countVote(uint256 proposalId, address account, uint8 support, uint256 weight, bytes memory params) internal override(Governor, GovernorCountingSimple) returns (uint256) { return super._countVote(proposalId, account, support, weight, params); }
    function state(uint256 proposalId) public view override(Governor, GovernorTimelockControl) returns (ProposalState) { return super.state(proposalId); }
    function proposalNeedsQueuing(uint256 proposalId) public view override(Governor, GovernorTimelockControl) returns (bool) { return super.proposalNeedsQueuing(proposalId); }
    function _queueOperations(uint256 proposalId, address[] memory targets, uint256[] memory values, bytes[] memory calldatas, bytes32 descriptionHash) internal override(Governor, GovernorTimelockControl) returns (uint48) { return super._queueOperations(proposalId, targets, values, calldatas, descriptionHash); }
    function _executeOperations(uint256 proposalId, address[] memory targets, uint256[] memory values, bytes[] memory calldatas, bytes32 descriptionHash) internal override(Governor, GovernorTimelockControl) { super._executeOperations(proposalId, targets, values, calldatas, descriptionHash); }
    function _cancel(address[] memory targets, uint256[] memory values, bytes[] memory calldatas, bytes32 descriptionHash) internal override(Governor, GovernorTimelockControl) returns (uint256) { return super._cancel(targets, values, calldatas, descriptionHash); }
    function _executor() internal view override(Governor, GovernorTimelockControl) returns (address) { return super._executor(); }
    function supportsInterface(bytes4 interfaceId) public view override(Governor) returns (bool) { return super.supportsInterface(interfaceId); }
}
