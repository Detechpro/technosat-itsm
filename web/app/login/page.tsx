import { redirect } from "next/navigation";

/** The sign-in form now lives on the home page. Old /login links are forwarded there with their query string. */
export default async function LoginRedirect({ searchParams }: { searchParams: Promise<Record<string, string | undefined>> }) {
  const sp = await searchParams;
  const qs = new URLSearchParams(
    Object.entries(sp).filter((e): e is [string, string] => e[1] !== undefined),
  ).toString();
  redirect(qs ? `/?${qs}` : "/");
}
