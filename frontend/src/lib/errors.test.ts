import { describe, expect, it } from "vitest";

import { errorMessage } from "./errors";

describe("errorMessage", () => {
  it("maps fastapi-users codes", () => {
    expect(errorMessage({ detail: "LOGIN_BAD_CREDENTIALS" })).toBe("Wrong email or password.");
    expect(errorMessage({ detail: { code: "REGISTER_INVALID_PASSWORD", reason: "Password must be at least 8 characters" } })).toBe(
      "Password must be at least 8 characters",
    );
  });

  it("passes plain string details through", () => {
    expect(errorMessage({ detail: "Project not found" })).toBe("Project not found");
  });

  it("formats pydantic validation errors", () => {
    expect(errorMessage({ detail: [{ loc: ["body", "source_url"], msg: "Value error, Please paste a valid YouTube video link" }] })).toBe(
      "Please paste a valid YouTube video link",
    );
    expect(errorMessage({ detail: [{ loc: ["body", "email"], msg: "Field required" }] })).toBe("email is required");
  });

  it("falls back for unknown shapes", () => {
    expect(errorMessage(null)).toMatch(/Something went wrong/);
    expect(errorMessage({ nope: 1 }, "fallback")).toBe("fallback");
  });
});
