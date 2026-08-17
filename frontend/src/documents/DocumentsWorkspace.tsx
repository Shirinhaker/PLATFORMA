import { CounterpartyFormView, CounterpartyListView } from "./CounterpartyViews";
import { DocumentComposeView } from "./DocumentComposeView";
import { DocumentDetailView } from "./DocumentDetailView";
import { DocumentListView } from "./DocumentListView";
import type { DocumentsProps } from "./DocumentsShared";
import { CenterView, ProfileView } from "./ProfileCenterViews";
import { useDocumentsController } from "./useDocumentsController";
import "./Documents.css";

export function Documents(props: DocumentsProps) {
  const controller = useDocumentsController(props);

  switch (controller.view) {
    case "profile":
      return <ProfileView controller={controller} />;
    case "center":
      return <CenterView controller={controller} />;
    case "counterparties":
      return <CounterpartyListView controller={controller} />;
    case "counterparty-form":
      return <CounterpartyFormView controller={controller} />;
    case "compose":
      return <DocumentComposeView controller={controller} />;
    case "list":
      return <DocumentListView controller={controller} />;
    case "document":
      return <DocumentDetailView controller={controller} />;
  }
}
