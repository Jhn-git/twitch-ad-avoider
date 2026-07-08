window.Components = window.Components || {};

window.Components.ToastStack = function ToastStack({ toasts }) {
  return (
    <div className="toast-stack" aria-live="polite">
      {toasts.map((toast) => (
        <div key={toast.id} className={`toast ${toast.kind || "info"}`}>
          {toast.message}
        </div>
      ))}
    </div>
  );
};
