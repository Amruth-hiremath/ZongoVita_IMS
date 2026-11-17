import {
  ButtonLink,
  Card,
  CardBody,
  CardHeader,
  KeyValue,
  PageHeader,
  Pill,
  SectionLabel,
  TBody,
  TD,
  TH,
  THead,
  TR,
  Table,
  cn,
} from "@ims/ui";
import { ArrowRight, Check, X } from "lucide-react";
import type { Metadata } from "next";

import { ActionButton } from "@/components/action-button";
import { getPlatformConfig } from "@/data/config";

import { ModuleFlags } from "./module-flags";

export const metadata: Metadata = { title: "Platform Config" };

/** Steps of the provisioning card, as drawn. */
const provisioning = [
  { title: "New database", detail: "created empty — fully isolated from day one" },
  { title: "Registry row", detail: "customer → license → database (F52)" },
  { title: "Wizard (F35)", detail: "enterprise → super admin → sites → users" },
];

/** F53 Platform Config. */
export default async function ConfigPage() {
  const page = await getPlatformConfig();

  return (
    <>
      <PageHeader
        title="Platform Config"
        actions={
          <>
            <ButtonLink href="/audit" className="bg-none bg-white">
              View change history → F54
            </ButtonLink>
            <ActionButton endpoint="PATCH /platform/v1/config (no such resource in the LLD yet)" variant="primary">
              Save configuration
            </ActionButton>
          </>
        }
      />

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-[minmax(0,1fr)_412px]">
        <div className="flex min-w-0 flex-col gap-6 lg:pt-5">
          <Card>
            <CardHeader title="Module flags — shipped to every tenant" action={<Pill tone="dark">{page.environment}</Pill>} />
            <CardBody className="pt-5">
              <ModuleFlags flags={page.module_flags} />
            </CardBody>
          </Card>

          <Card>
            <CardHeader title="Environment rails" />
            <CardBody className="pb-8 pr-10 pt-3">
              <dl className="[&_dd]:text-gray-700">
                {page.environment_rails.map((row) => (
                  <KeyValue key={row.label} label={row.label} className="py-1">
                    {row.value}
                  </KeyValue>
                ))}
              </dl>
            </CardBody>
          </Card>

          <Card>
            <CardHeader title="Provisioning a new enterprise — zero touch on existing customers" />
            <CardBody className="pb-7 pt-2">
              <ol className="grid grid-cols-1 gap-4 lg:grid-cols-3 lg:gap-0">
                {provisioning.map((step, index) => (
                  <li key={step.title} className="min-w-0">
                    <div className="flex items-center">
                      <span
                        className={cn(
                          "flex size-6 shrink-0 items-center justify-center rounded-full text-[10.5px] font-semibold",
                          index === 0 ? "bg-blue-600 text-white" : "border-[1.4px] border-gray-300 bg-white text-gray-600",
                        )}
                      >
                        {index + 1}
                      </span>
                      {index < provisioning.length - 1 ? (
                        <span aria-hidden className="relative mx-1 hidden h-px flex-1 bg-gray-300 lg:block">
                          <ArrowRight className="absolute left-1/2 top-1/2 size-3 -translate-1/2 bg-white text-gray-400" strokeWidth={1.6} />
                        </span>
                      ) : null}
                    </div>
                    <p className="mt-3 text-[12.5px] font-semibold text-gray-900">{step.title}</p>
                    <p className="mt-0.5 max-w-[160px] text-[10.5px] leading-[14px] text-gray-500">{step.detail}</p>
                  </li>
                ))}
              </ol>
            </CardBody>
          </Card>
        </div>

        <div className="flex min-w-0 flex-col gap-6">
          <div>
            <SectionLabel className="mb-2">Plan entitlement rails</SectionLabel>
            <Table className="[&_td]:px-2.5 [&_th]:px-2.5">
              <THead>
                <TR>
                  <TH>Rail</TH>
                  <TH>Starter</TH>
                  <TH>Growth</TH>
                  <TH>Enterprise</TH>
                </TR>
              </THead>
              <TBody zebra>
                {page.plan_rails.map((row) => (
                  <TR key={row.rail}>
                    <TD strong className="h-[38px] whitespace-nowrap">
                      {row.rail}
                    </TD>
                    <TD muted className="h-[38px] whitespace-nowrap">
                      {row.starter}
                    </TD>
                    <TD muted className="h-[38px] whitespace-nowrap">
                      {row.growth}
                    </TD>
                    <TD muted className="h-[38px] whitespace-nowrap">
                      {row.enterprise}
                    </TD>
                  </TR>
                ))}
              </TBody>
            </Table>
          </div>

          <Card>
            <CardHeader title="Tenant override boundary" />
            <CardBody className="pb-7 pt-3">
              <p className="label-caps text-green-700">Tenants may tune</p>
              <ul className="mt-1 space-y-1.5 text-[11.5px] text-gray-700">
                {page.tenants_may_tune.map((line) => (
                  <li key={line} className="flex items-center gap-2.5">
                    <Check aria-hidden className="size-3 shrink-0 text-green-700" strokeWidth={2} />
                    {line}
                  </li>
                ))}
              </ul>
              <p className="label-caps mt-4 text-red-700">Tenants may not touch</p>
              <ul className="mt-1 space-y-1.5 text-[11.5px] text-gray-700">
                {page.tenants_may_not_touch.map((line) => (
                  <li key={line} className="flex items-center gap-2.5">
                    <X aria-hidden className="size-3 shrink-0 text-red-700" strokeWidth={2} />
                    {line}
                  </li>
                ))}
              </ul>
            </CardBody>
          </Card>
        </div>
      </div>
    </>
  );
}
