// Territory scope for CRM queries: `null` means every account (sales managers); a list of territories limits rows to
// accounts in those states (sales reps). Anything else is a bug, so it fails closed instead of returning everything.
export function checkScope(scope) {
  if (scope === null) return null;
  if (!Array.isArray(scope) || !scope.every((t) => typeof t === 'string')) {
    throw new Error('A territory scope is required: null for every territory, or a list of territories.');
  }
  return [...new Set(scope)];
}

// The SQL condition for a scope on `column` (an account's state, or a rep's region). Adds its parameters to `params`.
export function scopeSql(scope, params, column = 'a.state') {
  const territories = checkScope(scope);
  if (territories === null) return '1 = 1';
  if (!territories.length) return '1 = 0';
  territories.forEach((territory, i) => {
    params[`scope${i}`] = territory;
  });
  return `${column} IN (${territories.map((_, i) => `@scope${i}`).join(', ')})`;
}
