export const SAMPLE_VERCEL = `[12:01:03.221] Running build in Washington, D.C., USA (East) – iad1
[12:01:20.118] Installing dependencies...
[12:01:21.550] pnpm install --frozen-lockfile
[12:01:40.003] ▲ Next.js 15.1.0
[12:01:48.771] Failed to compile.
[12:01:48.772] ./src/app/page.tsx:3:1
[12:01:48.772] Module not found: Can't resolve '@/component/Header'
[12:01:48.801] > Build failed because of webpack errors
[12:01:48.855]  ELIFECYCLE  Command failed with exit code 1.
[12:01:48.900] Error: Command "pnpm run build" exited with 1
`;

export const SAMPLE_ENV = `▲ Vercel build
Next.js 15.1.0
Error: Missing environment variable: DATABASE_URL
    at src/lib/db.ts:12:11
DATABASE_URL=postgresql://admin:hunter2pass@db.example.com/prod
NEXTAUTH_SECRET=abcd1234efgh5678
ELIFECYCLE Command failed with exit code 1
`;
