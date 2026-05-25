import { cookies } from "next/headers";

export type Theme = "light" | "dark";

/** Read the user's theme from the `theme` cookie. Default light (Apple
 *  HIG defaults light; user can toggle dark via the toolbar). */
export async function getTheme(): Promise<Theme> {
  const c = await cookies();
  return c.get("theme")?.value === "dark" ? "dark" : "light";
}
