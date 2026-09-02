// SPDX-License-Identifier: MIT
pragma solidity ^0.8.26;

/// @notice Treasury-controlled governance authority for CryptoAID.
/// @dev This intentionally replaces token-voting Governor/IVotes governance per project authority decision.
contract CryptoAIDGovernance {
    address public immutable governanceAuthority;
    address public immutable timelock;

    event GovernanceAction(address indexed authority, address indexed target, uint256 value, bytes data, bytes result);

    constructor(address governanceAuthority_, address timelock_) {
        require(governanceAuthority_ != address(0), "ZERO_AUTHORITY");
        require(timelock_ != address(0) && timelock_.code.length > 0, "BAD_TIMELOCK");
        governanceAuthority = governanceAuthority_;
        timelock = timelock_;
    }

    modifier onlyGovernanceAuthority() {
        require(msg.sender == governanceAuthority, "NOT_AUTHORITY");
        _;
    }

    /// @notice Execute an already-authorized governance call from the treasury authority.
    /// @dev No delegatecall; target must be a deployed contract. Critical delayed actions should be routed through timelock.
    function execute(address target, uint256 value, bytes calldata data)
        external
        payable
        onlyGovernanceAuthority
        returns (bytes memory result)
    {
        require(target != address(0) && target.code.length > 0, "BAD_TARGET");
        require(msg.value == value, "VALUE_MISMATCH");
        (bool ok, bytes memory out) = target.call{value: value}(data);
        require(ok, "CALL_FAILED");
        emit GovernanceAction(msg.sender, target, value, data, out);
        return out;
    }
}
