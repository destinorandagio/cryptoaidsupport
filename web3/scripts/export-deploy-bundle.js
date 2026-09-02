const fs = require('fs');
const path = require('path');
const hre = require('hardhat');

async function main() {
  const fqns = await hre.artifacts.getAllFullyQualifiedNames();
  const own = fqns.filter(x => x.startsWith('contracts/CryptoAID'));
  const contracts = [];
  for (const fqn of own) {
    const artifact = await hre.artifacts.readArtifact(fqn);
    if (!artifact.bytecode || artifact.bytecode === '0x') continue;
    const ctor = artifact.abi.find(x => x.type === 'constructor');
    contracts.push({
      name: artifact.contractName,
      sourceName: artifact.sourceName,
      abi: artifact.abi,
      bytecode: artifact.bytecode,
      deployedBytecode: artifact.deployedBytecode,
      constructorInputs: ctor?.inputs || [],
      bytecodeKeccak256: hre.ethers.keccak256(artifact.bytecode),
      compiler: '0.8.26',
      evmVersion: 'cancun',
      chainId: 137,
      securityGate: 'REQUIRES_GREEN_CI_AND_HUMAN_APPROVAL'
    });
  }
  contracts.sort((a,b) => a.name.localeCompare(b.name));
  const bundle = {
    schema: 'cryptoaid.deploy-bundle.v1',
    generatedAt: new Date().toISOString(),
    target: { network: 'Polygon PoS Mainnet', chainId: 137, nativeGasToken: 'POL' },
    contracts
  };
  const outDir = path.join(__dirname, '..', 'deploy');
  fs.mkdirSync(outDir, { recursive: true });
  fs.writeFileSync(path.join(outDir, 'deploy-bundle.json'), JSON.stringify(bundle, null, 2));
  console.log(`Exported ${contracts.length} deployable CryptoAID artifacts.`);
}
main().catch(err => { console.error(err); process.exitCode = 1; });
