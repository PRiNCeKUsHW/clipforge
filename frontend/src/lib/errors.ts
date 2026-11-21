/** Turn FastAPI / fastapi-users error bodies into a sentence a person can read. */

const CODE_MESSAGES: Record<string, string> = {
  LOGIN_BAD_CREDENTIALS: "Wrong email or password.",
  LOGIN_USER_NOT_VERIFIED: "Please verify your email first.",
  REGISTER_USER_ALREADY_EXISTS: "An account with this email already exists.",
};

type ValidationItem = { loc?: (string | number)[]; msg?: string };

export function errorMessage(body: unknown, fallback = "Something went wrong. Please try again."): string {
  if (!body || typeof body !== "object") return fallback;
  const detail = (body as { detail?: unknown }).detail;

  if (typeof detail === "string") return CODE_MESSAGES[detail] ?? detail;

  // fastapi-users: {"detail": {"code": "REGISTER_INVALID_PASSWORD", "reason": "..."}}
  if (detail && typeof detail === "object" && !Array.isArray(detail)) {
    const { code, reason } = detail as { code?: string; reason?: string };
    if (reason) return reason;
    if (code) return CODE_MESSAGES[code] ?? code;
  }

  // Pydantic 422: [{"loc": ["body", "source_url"], "msg": "Value error, Please paste..."}]
  if (Array.isArray(detail) && detail.length > 0) {
    const first = detail[0] as ValidationItem;
    const msg = (first.msg ?? "").replace(/^Value error, /, "");
    const field = first.loc?.filter((p) => p !== "body").join(".");
    if (!msg) return fallback;
    return msg.startsWith("Field required") && field ? `${field} is required` : msg;
  }
  return fallback;
}
