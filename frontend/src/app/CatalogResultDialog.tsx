import { useEffect, useState } from "react";
import type { PublicCatalogItem } from "../api/types";
import { CatalogItemDetails } from "../legacy/public/CatalogItemDetails";
import type { CatalogItemCardProps } from "../legacy/public/CatalogItemActions";
import { ItemDetailsDialog } from "../legacy/public/ItemDetailsDialog";
import type { AppApi } from "./app-api";

type Props = Omit<CatalogItemCardProps, "item"> & {
  api: AppApi;
  publicId: string;
  onClose(): void;
};

export function CatalogResultDialog({ api, publicId, onClose, ...actions }: Props) {
  const [item, setItem] = useState<PublicCatalogItem | null>(null);
  const [error, setError] = useState("");
  const [attempt, setAttempt] = useState(0);
  useEffect(() => {
    let active = true;
    setError("");
    setItem(null);
    api
      .getCatalogItem?.(publicId)
      .then((result) => {
        if (active) setItem(result);
      })
      .catch((reason: unknown) => {
        if (active)
          setError(
            reason instanceof Error ? reason.message : "Ma’lumotni yuklab bo‘lmadi.",
          );
      });
    return () => {
      active = false;
    };
  }, [api, publicId, attempt]);
  if (item) return <CatalogItemDetails {...actions} item={item} onClose={onClose} />;
  return (
    <ItemDetailsDialog onClose={onClose}>
      {error ? (
        <>
          <p role="alert">{error}</p>
          <button
            className="btn btn-soft"
            type="button"
            onClick={() => setAttempt((value) => value + 1)}
          >
            Qayta urinish
          </button>
        </>
      ) : (
        <p role="status">Yuklanmoqda...</p>
      )}
    </ItemDetailsDialog>
  );
}
