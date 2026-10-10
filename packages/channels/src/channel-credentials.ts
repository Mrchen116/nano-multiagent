import { createHash, createPrivateKey, createPublicKey, generateKeyPairSync, diffieHellman, hkdfSync, randomBytes, createCipheriv, createDecipheriv, type KeyObject } from 'node:crypto';
import { readFile, mkdir, open, rename, chmod } from 'node:fs/promises';
import { dirname } from 'node:path';

const algorithm = 'X25519-HKDF-SHA256-AES-256-GCM';
const context = 'nano-multiagent/channel-envelope-v1';
export interface ChannelAad { owner_id: string; node_id: string; agent_id: string; channel_id: string; provider: string; credential_revision: number }
export interface CredentialEnvelope { version: number; algorithm: string; ephemeral_public_key: string; salt: string; nonce: string; ciphertext: string }

/** Wire-compatible node key; plaintext credentials never leave its local caller. */
export class ChannelKey {
  private constructor(private readonly key: KeyObject) {}
  static async load(path: string): Promise<ChannelKey> {
    let pem: string;
    try { pem = await readFile(path, 'utf8'); }
    catch (error) {
      if ((error as NodeJS.ErrnoException).code !== 'ENOENT') throw error;
      const pair = generateKeyPairSync('x25519'); pem = pair.privateKey.export({ type: 'pkcs8', format: 'pem' }) as string;
      await mkdir(dirname(path), { recursive: true }); const temporary = `${path}.${randomBytes(8).toString('hex')}.tmp`;
      const file = await open(temporary, 'wx', 0o600);
      try { await file.writeFile(pem); await file.sync(); } finally { await file.close(); }
      await rename(temporary, path); const directory = await open(dirname(path), 'r'); try { await directory.sync(); } finally { await directory.close(); }
    }
    await chmod(path, 0o600); const key = createPrivateKey(pem);
    if (key.asymmetricKeyType !== 'x25519') throw new Error('Channel credential key must be X25519');
    return new ChannelKey(key);
  }
  get registration() {
    const raw = publicBytes(this.key);
    return { credential_key_id: `sha256:${createHash('sha256').update(raw).digest('hex')}`, credential_algorithm: algorithm, credential_public_key: raw.toString('base64') };
  }
  /** Decrypt only the independent device-binding challenge purpose. */
  openBinding(envelope: CredentialEnvelope & {aad:{purpose:string}}):string {
    if(envelope.aad.purpose!=='device-binding')throw new Error('Invalid binding challenge purpose');
    const remote=createPublicKey({key:{kty:'OKP',crv:'X25519',x:Buffer.from(envelope.ephemeral_public_key,'base64').toString('base64url')},format:'jwk'});
    const shared=diffieHellman({privateKey:this.key,publicKey:remote});
    const key=Buffer.from(hkdfSync('sha256',shared,Buffer.from(envelope.salt,'base64'),'nano-multiagent/device-binding-v1',32));
    const ciphertext=Buffer.from(envelope.ciphertext,'base64');const decipher=createDecipheriv('aes-256-gcm',key,Buffer.from(envelope.nonce,'base64'));
    decipher.setAAD(canonical(envelope.aad));decipher.setAuthTag(ciphertext.subarray(-16));
    return Buffer.concat([decipher.update(ciphertext.subarray(0,-16)),decipher.final()]).toString('utf8');
  }
  seal(secret: Record<string, string>, aad: ChannelAad): CredentialEnvelope {
    const ephemeral = generateKeyPairSync('x25519'); const salt = randomBytes(32); const nonce = randomBytes(12);
    const shared = diffieHellman({ privateKey: ephemeral.privateKey, publicKey: createPublicKey(this.key) });
    const key = Buffer.from(hkdfSync('sha256', shared, salt, context, 32)); const cipher = createCipheriv('aes-256-gcm', key, nonce);
    cipher.setAAD(canonical(aad)); const encrypted = Buffer.concat([cipher.update(canonical(secret)), cipher.final(), cipher.getAuthTag()]);
    return { version: 1, algorithm, ephemeral_public_key: publicBytes(ephemeral.privateKey).toString('base64'), salt: salt.toString('base64'), nonce: nonce.toString('base64'), ciphertext: encrypted.toString('base64') };
  }
  open(envelope: CredentialEnvelope, aad: ChannelAad): Record<string, string> {
    try {
      if (envelope.version !== 1 || envelope.algorithm !== algorithm) throw new Error('Unsupported envelope');
      const remote = createPublicKey({ key: { kty: 'OKP', crv: 'X25519', x: Buffer.from(envelope.ephemeral_public_key, 'base64').toString('base64url') }, format: 'jwk' });
      const shared = diffieHellman({ privateKey: this.key, publicKey: remote });
      const key = Buffer.from(hkdfSync('sha256', shared, Buffer.from(envelope.salt, 'base64'), context, 32));
      const encrypted = Buffer.from(envelope.ciphertext, 'base64'); const decipher = createDecipheriv('aes-256-gcm', key, Buffer.from(envelope.nonce, 'base64'));
      decipher.setAAD(canonical(aad)); decipher.setAuthTag(encrypted.subarray(-16));
      const decoded: unknown = JSON.parse(Buffer.concat([decipher.update(encrypted.subarray(0, -16)), decipher.final()]).toString('utf8'));
      if (!decoded || typeof decoded !== 'object' || Array.isArray(decoded) || !Object.values(decoded).every(value => typeof value === 'string')) throw new Error('Invalid credentials');
      return decoded as Record<string, string>;
    } catch { throw new Error('credential envelope invalid'); }
  }
}
function publicBytes(privateKey: KeyObject): Buffer { return Buffer.from(createPublicKey(privateKey).export({ format: 'jwk' }).x!, 'base64url'); }
function canonical(value: object): Buffer { return Buffer.from(JSON.stringify(Object.fromEntries(Object.entries(value).sort(([a], [b]) => a < b ? -1 : a > b ? 1 : 0)))); }
