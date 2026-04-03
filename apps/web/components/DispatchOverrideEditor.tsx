"use client";

import type { DcStockContract, LorryState, WarehouseStockItem } from "@/lib/types";

export type EditableItem = { clientId: string; sku_id: number; quantity: number };
export type EditableStop = { clientId: string; dc_id: number; stop_sequence: number; items: EditableItem[] };
export type EditableRun = { clientId: string; lorry_id: number; dispatch_day: number; stops: EditableStop[] };

type DispatchOverrideEditorProps = {
  draftRuns: EditableRun[];
  lorryOptions: LorryState[];
  dcOptions: DcStockContract[];
  skuOptions: WarehouseStockItem[];
  onAddRun: () => void;
  onRemoveRun: (clientId: string) => void;
  onUpdateRun: (clientId: string, updater: (current: EditableRun) => EditableRun) => void;
  onUpdateStop: (
    runClientId: string,
    stopClientId: string,
    updater: (current: EditableStop) => EditableStop
  ) => void;
  onRemoveStop: (runClientId: string, stopClientId: string) => void;
  onAddStop: (runClientId: string) => void;
  onAddItem: (runClientId: string, stopClientId: string) => void;
  onRemoveItem: (runClientId: string, stopClientId: string, itemClientId: string) => void;
};

function describeLorry(lorry: LorryState) {
  return `${lorry.registration} | ${lorry.lorry_type} | cap ${lorry.capacity_units} | D1 ${lorry.day1_status} | D2 ${lorry.day2_status}`;
}

export function DispatchOverrideEditor({
  draftRuns,
  lorryOptions,
  dcOptions,
  skuOptions,
  onAddRun,
  onRemoveRun,
  onUpdateRun,
  onUpdateStop,
  onRemoveStop,
  onAddStop,
  onAddItem,
  onRemoveItem,
}: DispatchOverrideEditorProps) {
  return (
    <div className="editor-grid">
      {draftRuns.map((run) => {
        const selectedLorry = lorryOptions.find((lorry) => lorry.lorry_id === run.lorry_id);
        return (
          <article key={run.clientId} className="editor-run">
            <div className="editor-run-header">
              <div>
                <h4>Editable Run</h4>
                <p className="subtle-text">
                  Dispatch day and lorry assignment are part of the override payload.
                </p>
              </div>
              <button type="button" className="button button-ghost" onClick={() => onRemoveRun(run.clientId)}>
                Remove Run
              </button>
            </div>

            <div className="field-grid">
              <div className="form-field">
                <label htmlFor={`${run.clientId}-lorry`}>Lorry</label>
                <select
                  id={`${run.clientId}-lorry`}
                  value={run.lorry_id}
                  onChange={(event) =>
                    onUpdateRun(run.clientId, (current) => ({
                      ...current,
                      lorry_id: Number(event.target.value),
                    }))
                  }
                >
                  {lorryOptions.map((lorry) => (
                    <option key={lorry.lorry_id} value={lorry.lorry_id}>
                      {describeLorry(lorry)}
                    </option>
                  ))}
                </select>
              </div>

              <div className="form-field">
                <label htmlFor={`${run.clientId}-day`}>Dispatch Day</label>
                <select
                  id={`${run.clientId}-day`}
                  value={run.dispatch_day}
                  onChange={(event) =>
                    onUpdateRun(run.clientId, (current) => ({
                      ...current,
                      dispatch_day: Number(event.target.value),
                    }))
                  }
                >
                  <option value={1}>Day 1</option>
                  <option value={2}>Day 2</option>
                </select>
              </div>
            </div>

            {selectedLorry ? (
              <p className="subtle-text">
                Horizon status: Day 1 {selectedLorry.day1_status}, Day 2 {selectedLorry.day2_status}.
              </p>
            ) : null}

            <div className="stack-list">
              {run.stops.map((stop) => (
                <article key={stop.clientId} className="editor-stop">
                  <div className="editor-stop-header">
                    <div>
                      <h4>Stop Payload</h4>
                      <p className="subtle-text">
                        Each run may contain up to two DC stops after validation.
                      </p>
                    </div>
                    <button
                      type="button"
                      className="button button-ghost"
                      onClick={() => onRemoveStop(run.clientId, stop.clientId)}
                    >
                      Remove Stop
                    </button>
                  </div>

                  <div className="field-grid">
                    <div className="form-field">
                      <label htmlFor={`${stop.clientId}-dc`}>Distribution Center</label>
                      <select
                        id={`${stop.clientId}-dc`}
                        value={stop.dc_id}
                        onChange={(event) =>
                          onUpdateStop(run.clientId, stop.clientId, (current) => ({
                            ...current,
                            dc_id: Number(event.target.value),
                          }))
                        }
                      >
                        {dcOptions.map((dc) => (
                          <option key={dc.dc_id} value={dc.dc_id}>
                            {dc.dc_code} - {dc.dc_name}
                          </option>
                        ))}
                      </select>
                    </div>

                    <div className="form-field">
                      <label htmlFor={`${stop.clientId}-sequence`}>Stop Sequence</label>
                      <input
                        id={`${stop.clientId}-sequence`}
                        type="number"
                        min={1}
                        value={stop.stop_sequence}
                        onChange={(event) =>
                          onUpdateStop(run.clientId, stop.clientId, (current) => ({
                            ...current,
                            stop_sequence: Number(event.target.value),
                          }))
                        }
                      />
                    </div>
                  </div>

                  <div className="items-list">
                    {stop.items.map((item) => (
                      <div key={item.clientId} className="item-row">
                        <div className="form-field">
                          <label htmlFor={`${item.clientId}-sku`}>SKU</label>
                          <select
                            id={`${item.clientId}-sku`}
                            value={item.sku_id}
                            onChange={(event) =>
                              onUpdateStop(run.clientId, stop.clientId, (current) => ({
                                ...current,
                                items: current.items.map((currentItem) =>
                                  currentItem.clientId === item.clientId
                                    ? { ...currentItem, sku_id: Number(event.target.value) }
                                    : currentItem
                                ),
                              }))
                            }
                          >
                            {skuOptions.map((sku) => (
                              <option key={sku.sku_id} value={sku.sku_id}>
                                {sku.sku_code} - {sku.sku_name}
                              </option>
                            ))}
                          </select>
                        </div>

                        <div className="form-field">
                          <label htmlFor={`${item.clientId}-qty`}>Quantity</label>
                          <input
                            id={`${item.clientId}-qty`}
                            type="number"
                            min={0}
                            value={item.quantity}
                            onChange={(event) =>
                              onUpdateStop(run.clientId, stop.clientId, (current) => ({
                                ...current,
                                items: current.items.map((currentItem) =>
                                  currentItem.clientId === item.clientId
                                    ? { ...currentItem, quantity: Number(event.target.value) }
                                    : currentItem
                                ),
                              }))
                            }
                          />
                        </div>

                        <button
                          type="button"
                          className="button button-ghost"
                          onClick={() => onRemoveItem(run.clientId, stop.clientId, item.clientId)}
                        >
                          Remove Item
                        </button>
                      </div>
                    ))}
                  </div>

                  <div className="toolbar">
                    <button
                      type="button"
                      className="button button-secondary"
                      onClick={() => onAddItem(run.clientId, stop.clientId)}
                    >
                      Add Item
                    </button>
                  </div>
                </article>
              ))}
            </div>

            <div className="toolbar">
              <button
                type="button"
                className="button button-secondary"
                onClick={() => onAddStop(run.clientId)}
              >
                Add Stop
              </button>
            </div>
          </article>
        );
      })}

      <div className="section-card-actions">
        <button type="button" className="button button-secondary" onClick={onAddRun}>
          Add Run
        </button>
      </div>
    </div>
  );
}
