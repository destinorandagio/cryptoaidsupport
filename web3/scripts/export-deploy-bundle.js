const fs = require('fs');
const path = require('path');
const hre = require('hardhat');

const REQUIRED_CASE_AUTHORITY = 'CHAT02_EVIDENCE_PAYMENT_ENTITLEMENT';
const REQUIRED_MVP_SETTLEMENT = 'SANDBOX_ONLY_NO_CONTRACT_DEPLOY';
const FORBIDDEN_CASE_CONTRACT = 'CryptoAIDCasePayment';

function loadReleasePolicy() {
  const planPath = path.join(__dirname, '..', 'deploy', 'deployment-plan.json');
  const plan = JSON.parse(fs.readFileSync(planPath, 'utf8'));
  if (Number(plan.chainId) !== 137) throw new Error('MVP deploy bundle requires Polygon chainId 137');
  if (plan.humanGate !== true) throw new Error('MVP deploy bundle requires humanGate=true');
  if (plan.mvpCaseSettlement !== REQUIRED_MVP_SETTLEMENT) throw new Error('MVP Case settlement must remain sandbox-only');
  if (plan.casePaymentAuthority !== REQUIRED_CASE_AUTHORITY) throw new Error('CHAT02 must remain the Case-payment authority');
  if ('paymentAsset' in plan) throw new Error('MVP deployment plan must not define a Case paymentAsset');
  const exclusions = new Set(plan.mvpReleaseExclusions || []);
  if (!exclusions.has(FORBIDDEN_CASE_CONTRACT)) throw new Error(`${FORBIDDEN_CASE_CONTRACT} must be excluded from the MVP release`);
  const forbiddenStep = (plan.steps || []).find(step => step.contract === FORBIDDEN_CASE_CONTRACT);
  if (!forbiddenStep || forbiddenStep.enabled !== false || forbiddenStep.phase !== 'POST_MVP') throw new Error(`${FORBIDDEN_CASE_CONTRACT} must be disabled and POST_MVP`);
  return { plan, exclusions };
}

async function main() {
  const { plan, exclusions } = loadReleasePolicy();
  const fqns = await hre.artifacts.getAllFullyQualifiedNames();
  const own = fqns.filter(x => x.startsWith('contracts/CryptoAID'));
  const contracts = [];
  for (const fqn of own) {
    const artifact = await hre.artifacts.readArtifact(fqn);
    if (!artifact.bytecode || artifact.bytecode === '0x') continue;
    if (exclusions.has(artifact.contractName)) continue;
    const ctor = artifact.abi.find(x => x.type === 'constructor');
    contracts.push({name:artifact.contractName,sourceName:artifact.sourceName,abi:artifact.abi,bytecode:artifact.bytecode,deployedBytecode:artifact.deployedBytecode,constructorInputs:ctor?.inputs||[],bytecodeKeccak256:hre.ethers.keccak256(artifact.bytecode),compiler:'0.8.26',evmVersion:'cancun',chainId:137,securityGate:'REQUIRES_GREEN_CI_AND_HUMAN_APPROVAL'});
  }
  contracts.sort((a,b)=>a.name.localeCompare(b.name));
  if (contracts.some(c=>c.name===FORBIDDEN_CASE_CONTRACT)) throw new Error(`Forbidden MVP Case-payment artifact exported: ${FORBIDDEN_CASE_CONTRACT}`);
  const bundle={schema:'cryptoaid.deploy-bundle.v1',generatedAt:new Date().toISOString(),target:{network:'Polygon PoS Mainnet',chainId:137,nativeGasToken:'POL'},mvpCaseSettlement:plan.mvpCaseSettlement,casePaymentAuthority:plan.casePaymentAuthority,mvpReleaseExclusions:[...exclusions].sort(),contracts};
  const outDir=path.join(__dirname,'..','deploy'); fs.mkdirSync(outDir,{recursive:true}); fs.writeFileSync(path.join(outDir,'deploy-bundle.json'),JSON.stringify(bundle,null,2));
  console.log(`Exported ${contracts.length} deployable CryptoAID artifacts; excluded ${[...exclusions].sort().join(', ') || 'none'}.`);
}
main().catch(err=>{console.error(err);process.exitCode=1;});
