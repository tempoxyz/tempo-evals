import { parseUnits, type Address, type Hex } from "viem";
import { generatePrivateKey } from "viem/accounts";
import { Actions, Account, createClient, http } from "viem/tempo";
import { tempoLocalnet } from "viem/tempo/chains";

function required(name: string): string {
  const value = process.env[name];
  if (!value) throw new Error(`${name} is required`);
  return value;
}

const root = Account.fromSecp256k1(required("TEMPO_PAYER_PRIVATE_KEY") as Hex);
const accessKey = Account.fromSecp256k1(generatePrivateKey(), {
  access: root,
});
const token = required("TEMPO_TOKEN") as Address;
const recipient = required("TEMPO_RECIPIENT") as Address;
const amount = parseUnits(required("TEMPO_AMOUNT"), Number(required("TEMPO_DECIMALS")));
const expiry = Math.floor(Date.now() / 1000) + 3600;

const clientConfig = {
  chain: tempoLocalnet,
  feeToken: token,
  transport: http(required("TEMPO_RPC_URL")),
};
const rootClient = createClient({
  ...clientConfig,
  account: root,
});

await Actions.faucet.fundSync(rootClient, {
  account: root.address,
});

const authorization = await Actions.accessKey.authorizeSync(rootClient, {
  accessKey,
  expiry,
});

const accessKeyClient = createClient({
  ...clientConfig,
  account: accessKey,
});

const transfer = await Actions.token.transferSync(accessKeyClient, {
  amount,
  to: recipient,
  token,
});

console.log(
  JSON.stringify(
    {
      accessKey: accessKey.accessKeyAddress,
      authorizationStatus: authorization.receipt.status,
      transferStatus: transfer.receipt.status,
      transferTransactionHash: transfer.receipt.transactionHash,
    },
    null,
    2,
  ),
);
