"use client";

import {
  Button,
  ButtonLink,
  Card,
  Checkbox,
  Field,
  Input,
  Modal,
  NoteBox,
  SectionLabel,
  Select,
  Tabs,
  Toggle,
} from "@ims/ui";
import { ChevronRight, Image as ImageIcon, Plus, ScanLine, Trash2 } from "lucide-react";
import { useId, useState, type ChangeEvent, type ReactNode } from "react";

import { ActionButton } from "@/components/action-button";
import type { AttributeType, ItemFormData } from "@/data/item-form";

const typeLabel: Record<AttributeType, string> = {
  text: "Text",
  number: "Number",
  dropdown: "Dropdown",
  date: "Date",
};

/** Upload limits drawn on the frame: "PNG / JPG up to 2 MB". */
const IMAGE_TYPES = ["image/png", "image/jpeg"];
const IMAGE_MAX_BYTES = 2 * 1024 * 1024;

function CardTitle({ children }: { children: ReactNode }) {
  return <h2 className="text-[13.5px] font-semibold text-gray-900">{children}</h2>;
}

/**
 * Body of F08. Every control is live in the browser; nothing is saved until POST /ui/v1/items
 * exists (the "Save item" button in the header says so).
 */
export function ItemForm({ data }: { data: ItemFormData }) {
  const id = useId();
  const { draft } = data;

  const [codeMode, setCodeMode] = useState<"auto" | "manual">("auto");
  const [manualCode, setManualCode] = useState("");
  const [name, setName] = useState(draft.name);
  const [uom, setUom] = useState(draft.uom);
  const [cost, setCost] = useState(draft.cost);
  const [path, setPath] = useState<string[]>(draft.category_path);
  const [barcode, setBarcode] = useState(draft.barcode);
  const [lifecycle, setLifecycle] = useState(draft.lifecycle);
  const [image, setImage] = useState<{ name: string } | { error: string } | null>(null);

  const [batch, setBatch] = useState(draft.batch_tracked);
  const [serial, setSerial] = useState(draft.serial_tracked);
  const [expiry, setExpiry] = useState(draft.expiry_tracked);
  const [shelfLife, setShelfLife] = useState(draft.shelf_life_months);
  const [minStock, setMinStock] = useState(draft.min_stock);
  const [maxStock, setMaxStock] = useState(draft.max_stock);

  const [vendor, setVendor] = useState(draft.vendor_code);
  const [vendorItemCode, setVendorItemCode] = useState(draft.vendor_item_code);
  const [rate, setRate] = useState(draft.rate);
  const [moq, setMoq] = useState(draft.moq);
  const [vendorLead, setVendorLead] = useState(draft.vendor_lead_days);

  const [addOpen, setAddOpen] = useState(false);
  const [newAttrName, setNewAttrName] = useState("");
  const [newAttrType, setNewAttrType] = useState<AttributeType>("text");
  const [newAttrRequired, setNewAttrRequired] = useState(true);

  const leadDays = Number(vendorLead);
  const totalLead =
    vendorLead.trim() !== "" && Number.isFinite(leadDays) ? `${data.internal_po_lead_days + leadDays} d` : "—";

  const onImage = (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) return;
    if (!IMAGE_TYPES.includes(file.type)) setImage({ error: `${file.name} is not a PNG or JPG.` });
    else if (file.size > IMAGE_MAX_BYTES) setImage({ error: `${file.name} is larger than 2 MB.` });
    else setImage({ name: file.name });
  };

  const closeAdd = () => {
    setAddOpen(false);
    setNewAttrName("");
    setNewAttrType("text");
    setNewAttrRequired(true);
  };

  return (
    <div className="grid grid-cols-1 gap-6 lg:grid-cols-[minmax(0,1fr)_412px]">
      {/* ------------------------------------------------------------------ left column */}
      <div className="flex min-w-0 flex-col gap-4">
        <Card className="px-4 pb-5 pt-4">
          <CardTitle>Basics</CardTitle>

          <SectionLabel className="mb-2 mt-6">Item code — auto running number or manual entry (Q6)</SectionLabel>
          <div className="flex flex-wrap items-center gap-4">
            <Tabs
              variant="segmented"
              value={codeMode}
              onChange={(value) => setCodeMode(value as "auto" | "manual")}
              className="h-10 w-[224px] bg-gray-50 [&>button]:h-8 [&>button]:flex-1"
              items={[
                { id: "auto", label: "Auto · running no." },
                { id: "manual", label: "Manual" },
              ]}
            />
            {codeMode === "auto" ? (
              <>
                <div className="w-[120px]">
                  <Input aria-label="Code prefix" value={data.numbering.prefix} readOnly className="font-semibold" />
                </div>
                <div className="flex h-10 w-[176px] items-center gap-4 rounded-md border-[1.4px] border-gray-300 bg-gray-50 px-3.5">
                  <span className="text-[11px] text-gray-500">next →</span>
                  <span className="text-[13px] font-semibold text-gray-900">{data.numbering.next_code}</span>
                </div>
              </>
            ) : (
              <div className="w-[312px] max-sm:w-full">
                <Input
                  aria-label="Item code"
                  placeholder="Type the item code"
                  value={manualCode}
                  onChange={(event) => setManualCode(event.target.value)}
                />
              </div>
            )}
          </div>

          <div className="mt-6 grid grid-cols-1 gap-x-6 gap-y-4 sm:grid-cols-[minmax(0,178fr)_minmax(0,200fr)_minmax(0,228fr)]">
            <Field label="Item name" htmlFor={`${id}-name`}>
              <Input id={`${id}-name`} value={name} onChange={(event) => setName(event.target.value)} />
            </Field>
            <Field label="Unit of measure" htmlFor={`${id}-uom`}>
              <Select id={`${id}-uom`} value={uom} onChange={(event) => setUom(event.target.value)}>
                {data.uoms.map((unit) => (
                  <option key={unit} value={unit}>
                    {unit}
                  </option>
                ))}
              </Select>
            </Field>
            <Field label="Cost (₹) · cost = price (Q4)" htmlFor={`${id}-cost`}>
              <Input
                id={`${id}-cost`}
                inputMode="decimal"
                value={cost}
                onChange={(event) => setCost(event.target.value)}
              />
            </Field>
          </div>

          <SectionLabel className="mb-2 mt-6">Category — four-level path</SectionLabel>
          <div className="grid grid-cols-1 gap-2 sm:grid-cols-[minmax(0,1fr)_auto_minmax(0,1fr)_auto_minmax(0,1fr)_auto_minmax(0,1fr)] sm:items-center sm:gap-0.5">
            {data.taxonomy.map((level, index) => (
              <div key={level.level} className="contents">
                {index > 0 ? (
                  <ChevronRight aria-hidden className="size-3 text-gray-400 max-sm:hidden" strokeWidth={1.6} />
                ) : null}
                <Select
                  aria-label={`Category level ${level.level}`}
                  value={path[index] ?? ""}
                  onChange={(event) =>
                    setPath((current) => {
                      const next = [...current];
                      next[index] = event.target.value;
                      return next;
                    })
                  }
                >
                  {level.options.map((option) => (
                    <option key={option.id} value={option.id}>
                      {option.name}
                    </option>
                  ))}
                </Select>
              </div>
            ))}
          </div>

          <label
            htmlFor={`${id}-image`}
            className="mt-5 flex w-[452px] max-w-full cursor-pointer items-center gap-4 rounded-md border-[1.4px] border-dashed border-blue-200 px-4 py-3 hover:bg-blue-50"
          >
            <ImageIcon aria-hidden className="size-5 shrink-0 text-blue-600" strokeWidth={1.6} />
            <span className="min-w-0">
              <span className="block text-[13px] font-semibold text-blue-600">Upload item image — PNG / JPG up to 2 MB</span>
              <span className="block text-[10.5px] text-gray-500">
                {image === null
                  ? "appears as thumbnail in list & detail (F07 · F09)"
                  : "error" in image
                    ? image.error
                    : `Selected: ${image.name}`}
              </span>
            </span>
            <input id={`${id}-image`} type="file" accept="image/png,image/jpeg" className="sr-only" onChange={onImage} />
          </label>

          <div className="mt-4 grid grid-cols-1 items-end gap-x-6 gap-y-4 sm:grid-cols-[minmax(0,1fr)_196px]">
            <div className="flex items-end gap-2.5">
              <Field label="Barcode (optional)" htmlFor={`${id}-barcode`} className="w-[300px] max-sm:flex-1">
                <Input
                  id={`${id}-barcode`}
                  placeholder="Scan or type EAN-13…"
                  value={barcode}
                  onChange={(event) => setBarcode(event.target.value)}
                  trailing={<ScanLine className="size-4" strokeWidth={1.6} />}
                />
              </Field>
              <ActionButton variant="soft" className="h-10 w-[100px]" endpoint="PATCH /ui/v1/items/{id} (generated barcode)">
                Generate
              </ActionButton>
            </div>
            <Field label="Lifecycle status" htmlFor={`${id}-lifecycle`}>
              <Select id={`${id}-lifecycle`} value={lifecycle} onChange={(event) => setLifecycle(event.target.value)}>
                {data.lifecycle.map((state) => (
                  <option key={state} value={state}>
                    {state}
                  </option>
                ))}
              </Select>
            </Field>
          </div>
        </Card>

        <Card className="px-4 pb-5 pt-4">
          <CardTitle>Tracking &amp; thresholds</CardTitle>
          <div className="mt-6 grid grid-cols-1 gap-x-8 gap-y-6 md:grid-cols-[240px_minmax(0,1fr)]">
            <div className="flex flex-col gap-10 pl-3.5 pt-1.5">
              <Toggle label="Batch / lot tracking — FR-9" checked={batch} onChange={(event) => setBatch(event.target.checked)} />
              <Toggle
                label="Serial tracking — optional"
                checked={serial}
                onChange={(event) => setSerial(event.target.checked)}
              />
            </div>
            <div>
              <Toggle
                label="Expiry tracking — where applicable (FB-05)"
                checked={expiry}
                onChange={(event) => setExpiry(event.target.checked)}
              />
              <div className="mt-4 grid max-w-[350px] grid-cols-2 gap-x-12 gap-y-3">
                <Field label="Shelf life" htmlFor={`${id}-shelf`}>
                  <Input
                    id={`${id}-shelf`}
                    inputMode="numeric"
                    value={shelfLife}
                    disabled={!expiry}
                    onChange={(event) => setShelfLife(event.target.value)}
                    trailing="months"
                  />
                </Field>
                <Field label="Min stock" htmlFor={`${id}-min`}>
                  <Input
                    id={`${id}-min`}
                    inputMode="decimal"
                    value={minStock}
                    onChange={(event) => setMinStock(event.target.value)}
                    trailing={uom}
                  />
                </Field>
                <Field label="Max stock" htmlFor={`${id}-max`} className="col-start-1 sm:ml-[98px] sm:w-[140px]">
                  <Input
                    id={`${id}-max`}
                    inputMode="decimal"
                    value={maxStock}
                    onChange={(event) => setMaxStock(event.target.value)}
                    trailing={uom}
                  />
                </Field>
              </div>
            </div>
          </div>
        </Card>
      </div>

      {/* ----------------------------------------------------------------- right column */}
      <div className="flex min-w-0 flex-col gap-4">
        <Card className="px-4 pb-4 pt-3.5">
          <div className="flex items-center justify-between gap-3">
            <CardTitle>Custom attributes (Q5)</CardTitle>
            <ButtonLink variant="link" href="/categories">
              Docs
            </ButtonLink>
          </div>
          <ul className="mt-5 flex flex-col gap-2.5">
            {data.attributes.map((attribute) => (
              <li
                key={attribute.id}
                className="grid grid-cols-[minmax(0,1fr)_110px_auto] items-center gap-3 rounded-md border-[1.4px] border-gray-300 px-3.5 py-2"
              >
                <span className="min-w-0">
                  <span className="block text-[13px] text-gray-900">{attribute.name}</span>
                  <span className="block text-[10.5px] text-gray-400">
                    {attribute.required ? "Required for this category" : "Optional for this category"}
                  </span>
                </span>
                <span className="text-[11.5px] text-gray-500">{typeLabel[attribute.type]}</span>
                <ActionButton
                  variant="link"
                  aria-label={`Remove ${attribute.name}`}
                  className="text-gray-400 hover:no-underline"
                  endpoint="PATCH /ui/v1/attribute-definitions/{id}"
                >
                  <Trash2 className="size-3.5" strokeWidth={1.6} />
                </ActionButton>
              </li>
            ))}
          </ul>
          <button
            type="button"
            onClick={() => setAddOpen(true)}
            className="mt-2.5 flex h-12 w-full items-center gap-4 rounded-md border-[1.4px] border-dashed border-blue-200 px-6 text-[12.5px] font-semibold text-blue-600 hover:bg-blue-50"
          >
            <Plus aria-hidden className="size-4" strokeWidth={1.8} />
            Add attribute — text, number, dropdown or date
          </button>
        </Card>

        <Card className="px-4 pb-4 pt-4">
          <CardTitle>Purchase &amp; vendor details (FB-26)</CardTitle>
          <Field label="Preferred vendor · F37" htmlFor={`${id}-vendor`} className="mt-4">
            <Select id={`${id}-vendor`} value={vendor} onChange={(event) => setVendor(event.target.value)}>
              {data.vendors.map((option) => (
                <option key={option.vendor_code} value={option.vendor_code}>
                  {option.name} · {option.vendor_code}
                </option>
              ))}
            </Select>
          </Field>
          <div className="mt-3 grid grid-cols-2 gap-x-5 gap-y-3">
            <Field label="Vendor item code" htmlFor={`${id}-vic`}>
              <Input id={`${id}-vic`} value={vendorItemCode} onChange={(event) => setVendorItemCode(event.target.value)} />
            </Field>
            <Field label={`Rate (₹) · rate list ${draft.rate_list}`} htmlFor={`${id}-rate`}>
              <Input id={`${id}-rate`} inputMode="decimal" value={rate} onChange={(event) => setRate(event.target.value)} />
            </Field>
            <Field label="MOQ" htmlFor={`${id}-moq`}>
              <Input
                id={`${id}-moq`}
                inputMode="decimal"
                value={moq}
                onChange={(event) => setMoq(event.target.value)}
                trailing={uom}
              />
            </Field>
            <Field label="Vendor lead · F38" htmlFor={`${id}-lead`}>
              <Input
                id={`${id}-lead`}
                inputMode="numeric"
                value={vendorLead}
                onChange={(event) => setVendorLead(event.target.value)}
                trailing="days"
              />
            </Field>
          </div>
          <NoteBox tone="blue" className="mt-6 px-4 py-2">
            <SectionLabel>Total lead time (FB-18)</SectionLabel>
            <p className="text-[12.5px] font-semibold text-gray-900">
              {data.internal_po_lead_days} d internal PO (manual) + {vendorLead.trim() === "" ? "—" : vendorLead} d vendor ={" "}
              {totalLead}
            </p>
          </NoteBox>
        </Card>
      </div>

      <Modal
        open={addOpen}
        onClose={closeAdd}
        title="Add attribute"
        footer={
          <>
            <ActionButton variant="primary" endpoint="POST /ui/v1/attribute-definitions">
              Add attribute
            </ActionButton>
            <Button onClick={closeAdd}>Cancel</Button>
          </>
        }
      >
        <div className="flex flex-col gap-4">
          <Field label="Attribute name" htmlFor={`${id}-attr-name`}>
            <Input
              id={`${id}-attr-name`}
              placeholder="e.g. Material"
              value={newAttrName}
              onChange={(event) => setNewAttrName(event.target.value)}
            />
          </Field>
          <Field label="Type" htmlFor={`${id}-attr-type`}>
            <Select
              id={`${id}-attr-type`}
              value={newAttrType}
              onChange={(event) => setNewAttrType(event.target.value as AttributeType)}
            >
              {(Object.keys(typeLabel) as AttributeType[]).map((type) => (
                <option key={type} value={type}>
                  {typeLabel[type]}
                </option>
              ))}
            </Select>
          </Field>
          <Checkbox
            label="Required for this category"
            checked={newAttrRequired}
            onChange={(event) => setNewAttrRequired(event.target.checked)}
          />
        </div>
      </Modal>
    </div>
  );
}
