import { useState, type ReactNode, type Ref } from "react";
import type { PublicProfileItem } from "../../api/types";
import { ItemDetailsDialog } from "./ItemDetailsDialog";

interface Props {
  groups: [string, PublicProfileItem[]][];
  focusItemPublicId?: string;
  focusItemRef: Ref<HTMLElement>;
  education: boolean;
  queueSupported: boolean;
  itemAction(item: PublicProfileItem): ReactNode;
}

export function PublicProfileItems({
  groups,
  focusItemPublicId,
  focusItemRef,
  education,
  queueSupported,
  itemAction,
}: Props) {
  const [selectedItem, setSelectedItem] = useState<PublicProfileItem | null>(null);
  return (
    <>
      {groups.map(([groupName, items]) => (
        <div className="item-group-block" key={groupName || "ungrouped"}>
          {groupName ? (
            <div className="item-group-head">
              <div className="item-group-title">
                <h3>{groupName}</h3>
                <p>{items.length} ta</p>
              </div>
            </div>
          ) : null}
          <div className="item-hrow">
            {items.map((item) => {
              const focused = item.public_id === focusItemPublicId;
              const queueEnabled =
                queueSupported && item.kind === "service" && item.queue_enabled;
              const queueCount = Math.max(0, Number(item.today_queue_count) || 0);
              return (
                <article
                  aria-current={focused ? "true" : undefined}
                  className={`item-card2 biz-prod-card${focused ? " is-search-target" : ""}`}
                  data-item-public-id={item.public_id}
                  key={item.public_id}
                  ref={focused ? focusItemRef : undefined}
                  tabIndex={focused ? -1 : undefined}
                >
                  <button
                    className="item-details-trigger"
                    type="button"
                    aria-label={`${item.name} haqida ma’lumot`}
                    aria-haspopup="dialog"
                    onClick={() => setSelectedItem(item)}
                  >
                    <div className="item-card2-img">
                      {item.image_url ? (
                        <img alt="" src={item.image_url} />
                      ) : (
                        <span>📦</span>
                      )}
                    </div>
                    <div className="name">{item.name}</div>
                    <div className="price">{item.price_text || "Narx kelishiladi"}</div>
                    {item.note ? <div className="note">{item.note}</div> : null}
                    {education ? (
                      <>
                        <div className="note">
                          {item.course_mode === "online"
                            ? "Onlayn"
                            : item.course_mode === "hybrid"
                              ? "Aralash"
                              : "Offline"}
                          {item.course_duration ? ` · ${item.course_duration}` : ""}
                          {item.lesson_duration
                            ? ` · ${item.lesson_duration} daqiqa`
                            : ""}
                        </div>
                        {item.age_from || item.age_to ? (
                          <div className="note">
                            Yosh: {item.age_from || 0}–{item.age_to || "+"}
                          </div>
                        ) : null}
                        <div className="kind">
                          {item.enrollment_status === "closed"
                            ? "Qabul yopiq"
                            : "Qabul ochiq"}
                        </div>
                      </>
                    ) : null}
                    {queueEnabled ? (
                      <div
                        className="idesc"
                        data-medical-queue-count={queueCount}
                        style={{
                          color: "var(--primary)",
                          fontWeight: 800,
                          marginTop: 3,
                        }}
                      >
                        👥 Bugungi navbat: {queueCount} ta
                      </div>
                    ) : null}
                  </button>
                  {itemAction(item)}
                </article>
              );
            })}
          </div>
        </div>
      ))}
      {selectedItem ? (
        <ItemDetailsDialog
          item={selectedItem}
          education={education}
          onClose={() => setSelectedItem(null)}
        >
          <div onClickCapture={() => setSelectedItem(null)}>
            {itemAction(selectedItem)}
          </div>
        </ItemDetailsDialog>
      ) : null}
    </>
  );
}
