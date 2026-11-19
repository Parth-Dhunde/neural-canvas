/** Open a hidden file input from a direct user gesture (Linux portal-safe). */
export function openFilePicker(input: HTMLInputElement | null): boolean {
  if (!input) {
    return false;
  }

  input.value = "";
  try {
    input.click();
    return true;
  } catch {
    return false;
  }
}
