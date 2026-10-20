export type FieldErrors = Record<string, string>;

export class ApiError extends Error {
  constructor(
    public readonly status: number,
    message: string,
    public readonly fields: FieldErrors = {},
    public readonly fieldNames: readonly string[] = [],
  ) {
    super(message);
    this.name = 'ApiError';
  }
}

interface ErrorContext {
  messages?: Partial<Record<number, string>>;
  fieldMessages?: FieldErrors;
}

// Features supply domain wording; the transport retains only validation keys,
// never raw server values that could contain credentials or internal details.
export async function withApiErrors<T>(operation: Promise<T>, context: ErrorContext): Promise<T> {
  try {
    return await operation;
  } catch (failure) {
    if (!(failure instanceof ApiError)) throw failure;
    const fieldMessages = context.fieldMessages || {};
    const fields = Object.fromEntries(
      failure.fieldNames
        .filter((key) => Object.hasOwn(fieldMessages, key))
        .map((key) => [key, fieldMessages[key]]),
    );
    throw new ApiError(
      failure.status,
      context.messages?.[failure.status] || failure.message,
      { ...failure.fields, ...fields },
      failure.fieldNames,
    );
  }
}

export function errorMessage(error: unknown): string {
  return error instanceof ApiError
    ? error.message
    : 'Não foi possível concluir a ação. Tente novamente.';
}
