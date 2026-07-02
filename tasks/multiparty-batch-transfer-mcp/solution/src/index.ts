import { encodeFunctionData, parseAbi, parseUnits, type Address, type Hex } from "viem";
import { Account, Actions, createClient, http } from "viem/tempo";
import { tempoLocalnet } from "viem/tempo/chains";

function required(name: string): string {
  const value = process.env[name];
  if (!value) throw new Error(`${name} is required`);
  return value;
}

function list(name: string): string[] {
  return required(name).split(",").map((value) => value.trim()).filter(Boolean);
}

const rpcUrl = required("TEMPO_RPC_URL");
const token = required("TEMPO_TOKEN") as Address;
const decimals = Number(required("TEMPO_DECIMALS"));
const recipients = list("TEMPO_MULTI_RECIPIENTS") as Address[];
const amounts = list("TEMPO_MULTI_AMOUNTS");

if (recipients.length !== amounts.length) {
  throw new Error("TEMPO_MULTI_RECIPIENTS and TEMPO_MULTI_AMOUNTS must have the same length");
}

const account = Account.fromSecp256k1(required("TEMPO_PAYER_PRIVATE_KEY") as Hex);
const client = createClient({
  account,
  chain: tempoLocalnet,
  feeToken: token,
  transport: http(rpcUrl),
});

await Actions.faucet.fundSync(client, { account: account.address });

const tip20Abi = parseAbi(["function transfer(address to,uint256 amount) returns (bool)"]);
const calls = recipients.map((to, index) =>
  ({
    to: token,
    data: encodeFunctionData({
      abi: tip20Abi,
      functionName: "transfer",
      args: [to, parseUnits(amounts[index], decimals)],
    }),
  }),
);

const hash = await client.sendTransaction({ calls });
const receipt = await client.waitForTransactionReceipt({ hash });

console.log(JSON.stringify({ hash, status: receipt.status, calls: calls.length }, null, 2));
