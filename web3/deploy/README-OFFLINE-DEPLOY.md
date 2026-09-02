# CryptoAID Polygon Mainnet Offline Deployer

Target: Polygon PoS Mainnet (`chainId 137`). Payments/rewards use verified USDT; POL is gas only. Case Treasury: `0x3C320B3a0917fF44BF6551CDdee44402AFcF250C`.

## Package
Use the GitHub Actions artifact `cryptoaid-polygon-mainnet-offline-deployer`. It contains `index.html`, local `ethers.umd.min.js`, `deploy-bundle.json`, `deployment-plan.json`, this README and `checksums.sha256`.

## Procedure
1. Download and extract the artifact into one local folder.
2. Verify `checksums.sha256` before use. Do not edit package files after verification.
3. Open `index.html` locally in a browser with an injected EVM wallet.
4. Connect the wallet and switch to Polygon Mainnet 137. The wallet needs POL only for gas.
5. Load the local `deploy-bundle.json` and `deployment-plan.json` using the file selectors.
6. Enter and verify the canonical Polygon addresses for USDT, DUX and DRX. The deployer checks contract bytecode, symbol and decimals. Never invent token addresses.
7. Verify the displayed Case Treasury is exactly `0x3C320B3a0917fF44BF6551CDdee44402AFcF250C`.
8. Use Guided Deploy. Review constructor arguments and preflight/gas before every transaction.
9. Sign one deployment transaction at a time in the wallet. Never enter a seed phrase, mnemonic or private key in this page.
10. After each receipt, retain the contract address and transaction hash. The deployer persists the session locally and prevents accidental duplicate deployment.
11. At the end use COPY ALL RESULTS and download the full manifest and addresses JSON.
12. Paste COPY ALL RESULTS back into the CryptoAID project chat for post-deploy wiring/verification.

## Safety
This package does not auto-deploy and contains no private key. Blockchain operations still require wallet/RPC network connectivity. A successful internal build/static review is not a guarantee that contracts are free of vulnerabilities; independent external audit is recommended before material TVL.
