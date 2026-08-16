import { useEffect, useState } from "react";


export function AppToastV1656({ message }: { message: string }) {
  const [visible, setVisible] = useState(Boolean(message));

  useEffect(() => {
    if (!message) {
      setVisible(false);
      return undefined;
    }
    setVisible(true);
    const timer = window.setTimeout(() => setVisible(false), 2_600);
    return () => window.clearTimeout(timer);
  }, [message]);

  if (!message) return null;
  return (
    <div className={`app-toast${visible ? " on" : ""}`} role="status">
      {message}
    </div>
  );
}
