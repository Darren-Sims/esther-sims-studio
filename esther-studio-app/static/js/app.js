function copyText(elementId, btn) {
  const el = document.getElementById(elementId);
  const text = el.innerText || el.value;
  navigator.clipboard.writeText(text).then(() => {
    const original = btn.textContent;
    btn.textContent = "Copied!";
    setTimeout(() => { btn.textContent = original; }, 1500);
  });
}

function confirmDelete(message) {
  return confirm(message || "Are you sure? This can't be undone.");
}
