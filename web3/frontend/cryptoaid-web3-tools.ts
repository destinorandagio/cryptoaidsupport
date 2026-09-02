import { BrowserProvider, Contract, parseEther } from "ethers";

export const polygonMainnet = { chainId: 137, chainIdHex: "0x89", name: "Polygon PoS" } as const;

export type CryptoAIDAddresses = { rank: string; miner: string; duxStaking?: string; drxStaking?: string };

const rankAbi = [
  "function mint() returns(uint256)",
  "function tokenOf(address) view returns(uint256)",
  "function profile(uint256) view returns(uint64 xp,uint32 missions,uint16 rank,uint64 updatedAt)",
  "function rankMultiplierBps(address) view returns(uint256)"
];
const minerAbi = [
  "function missions(bytes32) view returns(uint64 xp,uint128 polReward,uint128 duxReward,uint128 drxReward,bool active)",
  "function consumedProof(bytes32) view returns(bool)"
];
const stakingAbi = [
  "function stake(uint256)", "function withdraw(uint256)", "function claim()", "function earned(address) view returns(uint256)", "function balanceOf(address) view returns(uint256)"
];

export async function connectCryptoAID(addresses: CryptoAIDAddresses) {
  if (!(window as any).ethereum) throw new Error("Web3 wallet not found");
  const eth = (window as any).ethereum;
  await eth.request({ method: "eth_requestAccounts" });
  const provider = new BrowserProvider(eth);
  const net = await provider.getNetwork();
  if (Number(net.chainId) !== polygonMainnet.chainId) {
    await eth.request({ method: "wallet_switchEthereumChain", params: [{ chainId: polygonMainnet.chainIdHex }] });
  }
  const signer = await provider.getSigner();
  return {
    provider, signer, account: await signer.getAddress(),
    rank: new Contract(addresses.rank, rankAbi, signer),
    miner: new Contract(addresses.miner, minerAbi, signer),
    duxStaking: addresses.duxStaking ? new Contract(addresses.duxStaking, stakingAbi, signer) : undefined,
    drxStaking: addresses.drxStaking ? new Contract(addresses.drxStaking, stakingAbi, signer) : undefined,
  };
}

export async function mintRank(rankContract: Contract) { const tx = await rankContract.mint(); return tx.wait(); }
export async function readRank(rankContract: Contract, user: string) { const id = await rankContract.tokenOf(user); if (id === 0n) return null; return { tokenId: id, profile: await rankContract.profile(id), multiplierBps: await rankContract.rankMultiplierBps(user) }; }
export async function stakeToken(pool: Contract, amountWei: bigint) { const tx = await pool.stake(amountWei); return tx.wait(); }
export async function claimRewards(pool: Contract) { const tx = await pool.claim(); return tx.wait(); }
export { parseEther };
