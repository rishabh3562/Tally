"use client";

import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { ArrowRight, ListChecks, MessageCircle, Upload } from "lucide-react";
import apiClient from "@/lib/api";
import { navigationItems } from "@/components/common/navigation";
import { formatINR } from "@/lib/format";
import type { TriageResponse } from "@/types";

/**
 * Home — the screen behind `/`, which until now was the create-next-app
 * template.
 *
 * Not a menu. The sidebar and the tab bar are already menus, and a third copy of
 * the same list would be the least useful thing this route could be. It names
 * the ONE next thing, because at any moment Tally knows what that is: nothing
 * imported yet, merchants sitting unlabelled, or everything current. The grid
 * below is the shortcut for when you already know where you're going.
 */

/** Cheap probe: one row is enough to answer "is there any data yet". Its own
 *  cache key, so it never collides with the dashboard's limit:1000 fetch —
 *  invalidating ["transactions"] still refreshes both. */
function useHasTransactions() {
  return useQuery({
    queryKey: ["transactions", "probe"],
    queryFn: async () => {
      const res = await apiClient.get("/api/transactions", { params: { limit: 1 } });
      return ((res.data?.data ?? []) as unknown[]).length > 0;
    },
  });
}

function NextStepSkeleton() {
  return (
    <div className="h-36 animate-pulse rounded-2xl bg-gray-100" aria-hidden="true" />
  );
}

export default function Home() {
  const { data: hasTransactions, isPending: probePending } = useHasTransactions();

  const { data: triage, isPending: triagePending } = useQuery<TriageResponse>({
    queryKey: ["triage"],
    queryFn: async () => (await apiClient.get("/api/transactions/triage")).data,
  });

  const loading = probePending || triagePending;
  const unlabelled = triage?.merchants ?? 0;

  return (
    <div className="mx-auto max-w-5xl space-y-8">
      <div>
        <h1 className="text-2xl font-bold text-gray-900 md:text-4xl">Start here</h1>
        <p className="mt-2 text-gray-600">
          Pick up the next thing, or jump straight to a screen.
        </p>
      </div>

      {/* The one next action. Order matters: you can't label what you haven't
          imported, and the numbers don't mean much until the labels are done. */}
      {loading ? (
        <NextStepSkeleton />
      ) : !hasTransactions ? (
        <NextStep
          icon={<Upload className="h-6 w-6" />}
          eyebrow="First step"
          title="Add a statement"
          body="Tally reads bank and UPI exports — PDF, CSV or Excel — and sorts the payments out for you."
          cta="Upload a statement"
          href="/upload"
        />
      ) : unlabelled > 0 ? (
        <NextStep
          icon={<ListChecks className="h-6 w-6" />}
          eyebrow="Needs you"
          title={`${unlabelled} merchant${unlabelled === 1 ? "" : "s"} without a label`}
          body={
            triage?.total_amount
              ? `${formatINR(triage.total_amount)} of spending isn't counted anywhere yet. Label a merchant once and every payment from it follows — now and on the next import.`
              : "Label a merchant once and every payment from it follows — now and on the next import."
          }
          cta="Start labelling"
          href="/triage"
        />
      ) : (
        <NextStep
          icon={<MessageCircle className="h-6 w-6" />}
          eyebrow="All caught up"
          title="Everything's labelled"
          body="Your breakdown is accurate. Ask where the money went, and Tally answers from the actual rows."
          cta="Ask a question"
          href="/chat"
        />
      )}

      <section>
        <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-gray-500">
          Go to
        </h2>
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {navigationItems.map(({ name, href, icon: Icon, description }) => (
            <Link
              key={href}
              href={href}
              className="group flex items-start gap-3 rounded-xl border border-gray-200 bg-white p-4 transition hover:border-blue-300 hover:shadow-md focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-500 focus-visible:ring-offset-2"
            >
              <span className="shrink-0 rounded-lg bg-blue-50 p-2 text-blue-600 transition group-hover:bg-blue-100">
                <Icon className="h-5 w-5" />
              </span>
              <span className="min-w-0">
                <span className="block font-semibold text-gray-900">{name}</span>
                <span className="block text-sm leading-snug text-gray-600">
                  {description}
                </span>
              </span>
            </Link>
          ))}
        </div>
      </section>
    </div>
  );
}

function NextStep({
  icon,
  eyebrow,
  title,
  body,
  cta,
  href,
}: {
  icon: React.ReactNode;
  eyebrow: string;
  title: string;
  body: string;
  cta: string;
  href: string;
}) {
  return (
    <section className="animate-rise rounded-2xl border border-gray-200 bg-white p-6 shadow-sm md:p-8">
      <div className="flex flex-col gap-5 md:flex-row md:items-center md:gap-6">
        <span className="flex h-12 w-12 shrink-0 items-center justify-center rounded-xl bg-blue-600 text-white">
          {icon}
        </span>
        <div className="min-w-0 flex-1">
          <p className="text-xs font-semibold uppercase tracking-wide text-blue-600">
            {eyebrow}
          </p>
          <h2 className="mt-1 text-xl font-bold text-gray-900 md:text-2xl">{title}</h2>
          <p className="mt-2 text-gray-600">{body}</p>
        </div>
        <Link
          href={href}
          className="inline-flex shrink-0 items-center justify-center gap-2 rounded-lg bg-blue-600 px-5 py-2.5 font-medium text-white transition hover:bg-blue-700 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-500 focus-visible:ring-offset-2"
        >
          {cta}
          <ArrowRight className="h-4 w-4" />
        </Link>
      </div>
    </section>
  );
}
