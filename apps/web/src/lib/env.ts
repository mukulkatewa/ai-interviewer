// Public config, read once. NEXT_PUBLIC_* values are inlined at build time, so
// each must be referenced literally (process.env[name] would be undefined in the browser).

function required(name: string, value: string | undefined): string {
  if (!value) throw new Error(`Missing environment variable ${name}. See apps/web/.env.example.`);
  return value;
}

export const env = {
  supabaseUrl: required("NEXT_PUBLIC_SUPABASE_URL", process.env.NEXT_PUBLIC_SUPABASE_URL),
  supabaseKey: required("NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY", process.env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY),
  apiUrl: required("NEXT_PUBLIC_API_URL", process.env.NEXT_PUBLIC_API_URL),
};
