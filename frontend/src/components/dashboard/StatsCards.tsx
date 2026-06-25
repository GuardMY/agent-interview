"use client";

import { Card, CardContent } from "@/components/ui/card";
import { useI18n } from "@/i18n";
import { Users, PlayCircle, Star } from "lucide-react";

interface Stats {
  total: number;
  active: number;
  avgScore: number | null;
}

export function StatsCards({ stats }: { stats: Stats }) {
  const { t } = useI18n();

  return (
    <div className="grid grid-cols-3 gap-4">
      <Card>
        <CardContent className="flex items-center gap-3 p-4">
          <Users className="h-5 w-5 text-blue-600" />
          <div>
            <p className="text-2xl font-bold">{stats.total}</p>
            <p className="text-xs text-gray-500">
              {t.dashboard.totalSessions}
            </p>
          </div>
        </CardContent>
      </Card>
      <Card>
        <CardContent className="flex items-center gap-3 p-4">
          <PlayCircle className="h-5 w-5 text-green-600" />
          <div>
            <p className="text-2xl font-bold">{stats.active}</p>
            <p className="text-xs text-gray-500">{t.dashboard.active}</p>
          </div>
        </CardContent>
      </Card>
      <Card>
        <CardContent className="flex items-center gap-3 p-4">
          <Star className="h-5 w-5 text-yellow-600" />
          <div>
            <p className="text-2xl font-bold">
              {stats.avgScore !== null ? stats.avgScore.toFixed(1) : "—"}
            </p>
            <p className="text-xs text-gray-500">{t.dashboard.avgScore}</p>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
