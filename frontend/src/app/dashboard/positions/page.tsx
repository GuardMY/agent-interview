"use client";

import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { useI18n } from "@/i18n";
import {
  listPositions,
  createPosition,
  updatePosition,
  archivePosition,
  ApiError,
} from "@/lib/api";
import { ArrowLeft, Plus, Pencil, Archive, Search } from "lucide-react";
import type { JobPositionListItem, SkillRequirement } from "@/types";

const LEVELS = [
  { key: "junior", labelKey: "levelJunior" as const },
  { key: "mid", labelKey: "levelMid" as const },
  { key: "senior", labelKey: "levelSenior" as const },
];

const SKILL_LEVELS = ["familiar", "proficient", "expert"] as const;
const SOFT_SKILL_LEVELS = ["low", "medium", "high"] as const;

export default function PositionsPage() {
  const { t } = useI18n();
  const router = useRouter();
  const [positions, setPositions] = useState<JobPositionListItem[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [search, setSearch] = useState("");
  const [levelFilter, setLevelFilter] = useState("");
  const [statusFilter, setStatusFilter] = useState("active");

  // Dialog state
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  // Form state
  const [title, setTitle] = useState("");
  const [department, setDepartment] = useState("");
  const [level, setLevel] = useState("mid");
  const [description, setDescription] = useState("");
  const [responsibilities, setResponsibilities] = useState("");
  const [focusAreas, setFocusAreas] = useState("");
  const [defaultQuestions, setDefaultQuestions] = useState(8);
  const [defaultDuration, setDefaultDuration] = useState(45);
  const [softSkills, setSoftSkills] = useState({
    teamwork: "medium",
    communication: "medium",
    ownership: "medium",
    leadership: "low",
  });
  const [requiredSkills, setRequiredSkills] = useState<SkillRequirement[]>([]);
  const [preferredSkills, setPreferredSkills] = useState<SkillRequirement[]>([]);

  const fetchPositions = useCallback(async () => {
    setError(null);
    setLoading(true);
    try {
      const res = await listPositions({
        page,
        size: 20,
        level: levelFilter || undefined,
        status: statusFilter || undefined,
        q: search || undefined,
      });
      setPositions(res.items);
      setTotal(res.total);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : t.positions.failLoad);
    } finally {
      setLoading(false);
    }
  }, [page, levelFilter, statusFilter, search, t]);

  useEffect(() => {
    fetchPositions();
  }, [fetchPositions]);

  const resetForm = () => {
    setTitle("");
    setDepartment("");
    setLevel("mid");
    setDescription("");
    setResponsibilities("");
    setFocusAreas("");
    setDefaultQuestions(8);
    setDefaultDuration(45);
    setSoftSkills({ teamwork: "medium", communication: "medium", ownership: "medium", leadership: "low" });
    setRequiredSkills([]);
    setPreferredSkills([]);
    setEditingId(null);
  };

  const openCreate = () => {
    resetForm();
    setDialogOpen(true);
  };

  const openEdit = async (pos: JobPositionListItem) => {
    try {
      const { getPosition } = await import("@/lib/api");
      const full = await getPosition(pos.id);
      setTitle(full.title);
      setDepartment(full.department);
      setLevel(full.level);
      setDescription(full.description || "");
      setResponsibilities((full.responsibilities || []).join("\n"));
      setFocusAreas((full.interview_focus_areas || []).join(", "));
      setDefaultQuestions(full.default_total_questions);
      setDefaultDuration(full.default_duration_minutes);
      setSoftSkills({
        teamwork: full.soft_skill_requirements?.teamwork || "medium",
        communication: full.soft_skill_requirements?.communication || "medium",
        ownership: full.soft_skill_requirements?.ownership || "medium",
        leadership: full.soft_skill_requirements?.leadership || "low",
      });
      setRequiredSkills(full.required_skills || []);
      setPreferredSkills(full.preferred_skills || []);
      setEditingId(pos.id);
      setError(null);
      setDialogOpen(true);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : t.positions.failLoad);
    }
  };

  const handleSave = async () => {
    if (!title.trim()) return;
    setSaving(true);
    setError(null);
    try {
      const data = {
        title: title.trim(),
        department: department.trim(),
        level,
        description: description.trim() || null,
        responsibilities: responsibilities
          .split("\n")
          .map((s) => s.trim())
          .filter(Boolean),
        required_skills: requiredSkills,
        preferred_skills: preferredSkills,
        soft_skill_requirements: softSkills,
        domain_knowledge: null,
        default_total_questions: defaultQuestions,
        default_duration_minutes: defaultDuration,
        interview_focus_areas: focusAreas
          .split(",")
          .map((s) => s.trim())
          .filter(Boolean),
      };

      if (editingId) {
        await updatePosition(editingId, data);
      } else {
        await createPosition(data);
      }
      setDialogOpen(false);
      resetForm();
      fetchPositions();
    } catch (e) {
      setError(
        e instanceof ApiError
          ? e.message
          : (editingId ? t.positions.failUpdate : t.positions.failCreate)
      );
    } finally {
      setSaving(false);
    }
  };

  const handleArchive = async (id: string) => {
    if (!confirm(t.positions.archiveConfirm)) return;
    try {
      await archivePosition(id);
      fetchPositions();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : t.positions.failUpdate);
    }
  };

  return (
    <div className="max-w-6xl mx-auto p-6 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">{t.positions.title}</h1>
          <p className="text-muted-foreground">{t.positions.subtitle}</p>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" onClick={() => router.push("/dashboard")}>
            <ArrowLeft className="mr-2 h-4 w-4" />
            {t.positions.backToDashboard}
          </Button>
          <Button onClick={openCreate}>
            <Plus className="mr-2 h-4 w-4" />
            {t.positions.newPosition}
          </Button>
        </div>
      </div>

      {/* Error Banner */}
      {error && (
        <div className="rounded-lg bg-red-50 p-3 text-sm text-red-700 flex items-center justify-between">
          <span>{error}</span>
          <button
            onClick={() => setError(null)}
            className="ml-3 text-red-400 hover:text-red-600 text-lg leading-none"
          >
            ×
          </button>
        </div>
      )}

      {/* Filters */}
      <div className="flex gap-3 flex-wrap">
        <div className="relative flex-1 min-w-[200px]">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
          <Input
            value={search}
            onChange={(e) => { setSearch(e.target.value); setPage(1); }}
            placeholder="Search positions..."
            className="pl-9"
          />
        </div>
        <select
          value={levelFilter}
          onChange={(e) => { setLevelFilter(e.target.value); setPage(1); }}
          className="rounded-md border px-3 py-2 text-sm bg-background"
        >
          <option value="">All Levels</option>
          {LEVELS.map(({ key, labelKey }) => (
            <option key={key} value={key}>{t.session[labelKey]}</option>
          ))}
        </select>
        <select
          value={statusFilter}
          onChange={(e) => { setStatusFilter(e.target.value); setPage(1); }}
          className="rounded-md border px-3 py-2 text-sm bg-background"
        >
          <option value="active">Active</option>
          <option value="archived">Archived</option>
          <option value="">All</option>
        </select>
      </div>

      {/* Position List */}
      {loading ? (
        <div className="text-center py-12 text-muted-foreground">{t.common.loading}</div>
      ) : positions.length === 0 ? (
        <div className="text-center py-12 text-muted-foreground">
          <p className="text-lg">{t.positions.noPositions}</p>
          <p className="text-sm">{t.positions.noPositionsHint}</p>
        </div>
      ) : (
        <div className="border rounded-lg overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-muted/50">
              <tr>
                <th className="text-left px-4 py-3">{t.positions.tableTitle}</th>
                <th className="text-left px-4 py-3">{t.positions.tableDepartment}</th>
                <th className="text-left px-4 py-3">{t.positions.tableLevel}</th>
                <th className="text-left px-4 py-3">{t.positions.tableQuestions}</th>
                <th className="text-right px-4 py-3">{t.positions.tableActions}</th>
              </tr>
            </thead>
            <tbody>
              {positions.map((pos) => (
                <tr key={pos.id} className="border-t hover:bg-muted/30">
                  <td className="px-4 py-3 font-medium">{pos.title}</td>
                  <td className="px-4 py-3 text-muted-foreground">{pos.department || "—"}</td>
                  <td className="px-4 py-3">
                    <span className="inline-flex items-center rounded-full bg-primary/10 px-2 py-0.5 text-xs font-medium text-primary">
                      {t.session[LEVELS.find((l) => l.key === pos.level)?.labelKey || "levelMid"]}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-muted-foreground">{pos.default_total_questions}</td>
                  <td className="px-4 py-3 text-right">
                    <div className="flex justify-end gap-1">
                      <Button size="sm" variant="ghost" onClick={() => openEdit(pos)}>
                        <Pencil className="h-4 w-4" />
                      </Button>
                      {pos.status === "active" && (
                        <Button size="sm" variant="ghost" onClick={() => handleArchive(pos.id)}>
                          <Archive className="h-4 w-4" />
                        </Button>
                      )}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Pagination */}
      {total > 20 && (
        <div className="flex justify-center gap-2">
          <Button
            variant="outline"
            size="sm"
            disabled={page <= 1}
            onClick={() => setPage((p) => p - 1)}
          >
            Previous
          </Button>
          <span className="px-3 py-1 text-sm text-muted-foreground">
            Page {page} of {Math.ceil(total / 20)}
          </span>
          <Button
            variant="outline"
            size="sm"
            disabled={page >= Math.ceil(total / 20)}
            onClick={() => setPage((p) => p + 1)}
          >
            Next
          </Button>
        </div>
      )}

      {/* Create / Edit Dialog */}
      <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
        <DialogContent className="max-h-[90vh] overflow-y-auto max-w-xl">
          <DialogHeader>
            <DialogTitle>
              {editingId ? t.positions.editTitle : t.positions.createTitle}
            </DialogTitle>
          </DialogHeader>
          <div className="space-y-4 pt-2">
            {/* Title */}
            <div>
              <label className="mb-1 block text-sm font-medium">{t.positions.titleLabel}</label>
              <Input
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                placeholder={t.positions.titlePlaceholder}
              />
            </div>

            {/* Department + Level */}
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="mb-1 block text-sm font-medium">{t.positions.departmentLabel}</label>
                <Input
                  value={department}
                  onChange={(e) => setDepartment(e.target.value)}
                  placeholder={t.positions.departmentPlaceholder}
                />
              </div>
              <div>
                <label className="mb-1 block text-sm font-medium">{t.positions.levelLabel}</label>
                <select
                  value={level}
                  onChange={(e) => setLevel(e.target.value)}
                  className="w-full rounded-md border px-3 py-2 text-sm bg-background"
                >
                  {LEVELS.map(({ key, labelKey }) => (
                    <option key={key} value={key}>{t.session[labelKey]}</option>
                  ))}
                </select>
              </div>
            </div>

            {/* Description */}
            <div>
              <label className="mb-1 block text-sm font-medium">{t.positions.descriptionLabel}</label>
              <Input
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                placeholder={t.positions.descriptionPlaceholder}
              />
            </div>

            {/* Responsibilities */}
            <div>
              <label className="mb-1 block text-sm font-medium">{t.positions.responsibilitiesLabel}</label>
              <textarea
                value={responsibilities}
                onChange={(e) => setResponsibilities(e.target.value)}
                placeholder={t.positions.responsibilitiesPlaceholder}
                rows={4}
                className="w-full rounded-md border px-3 py-2 text-sm bg-background resize-y"
              />
            </div>

            {/* Required Skills */}
            <div>
              <div className="flex items-center justify-between mb-1">
                <label className="text-sm font-medium">{t.positions.requiredSkillsLabel}</label>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() =>
                    setRequiredSkills((prev) => [
                      ...prev,
                      { skill: "", min_years: 0, level: "familiar" },
                    ])
                  }
                >
                  <Plus className="mr-1 h-3 w-3" />
                  {t.positions.addSkill}
                </Button>
              </div>
              {requiredSkills.length === 0 ? (
                <p className="text-xs text-muted-foreground py-2">No required skills added.</p>
              ) : (
                <div className="space-y-2">
                  {requiredSkills.map((sk, idx) => (
                    <div key={idx} className="flex gap-2 items-center">
                      <input
                        value={sk.skill}
                        onChange={(e) =>
                          setRequiredSkills((prev) =>
                            prev.map((s, i) =>
                              i === idx ? { ...s, skill: e.target.value } : s
                            )
                          )
                        }
                        placeholder={t.positions.skillName}
                        className="flex-1 rounded-md border px-2 py-1.5 text-sm bg-background"
                      />
                      <input
                        type="number"
                        min={0}
                        max={20}
                        value={sk.min_years}
                        onChange={(e) =>
                          setRequiredSkills((prev) =>
                            prev.map((s, i) =>
                              i === idx
                                ? { ...s, min_years: Math.max(0, Number(e.target.value)) }
                                : s
                            )
                          )
                        }
                        placeholder={t.positions.minYears}
                        className="w-16 rounded-md border px-2 py-1.5 text-sm bg-background"
                      />
                      <select
                        value={sk.level}
                        onChange={(e) =>
                          setRequiredSkills((prev) =>
                            prev.map((s, i) =>
                              i === idx ? { ...s, level: e.target.value } : s
                            )
                          )
                        }
                        className="w-24 rounded-md border px-2 py-1.5 text-sm bg-background"
                      >
                        {SKILL_LEVELS.map((lvl) => (
                          <option key={lvl} value={lvl}>
                            {t.positions[`level${lvl.charAt(0).toUpperCase() + lvl.slice(1)}` as keyof typeof t.positions] || lvl}
                          </option>
                        ))}
                      </select>
                      <button
                        type="button"
                        onClick={() =>
                          setRequiredSkills((prev) => prev.filter((_, i) => i !== idx))
                        }
                        className="text-red-400 hover:text-red-600 p-1"
                        title="Remove"
                      >
                        ×
                      </button>
                    </div>
                  ))}
                </div>
              )}
            </div>

            {/* Preferred Skills */}
            <div>
              <div className="flex items-center justify-between mb-1">
                <label className="text-sm font-medium">{t.positions.preferredSkillsLabel}</label>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() =>
                    setPreferredSkills((prev) => [
                      ...prev,
                      { skill: "", min_years: 0, level: "familiar" },
                    ])
                  }
                >
                  <Plus className="mr-1 h-3 w-3" />
                  {t.positions.addSkill}
                </Button>
              </div>
              {preferredSkills.length === 0 ? (
                <p className="text-xs text-muted-foreground py-2">No preferred skills added.</p>
              ) : (
                <div className="space-y-2">
                  {preferredSkills.map((sk, idx) => (
                    <div key={idx} className="flex gap-2 items-center">
                      <input
                        value={sk.skill}
                        onChange={(e) =>
                          setPreferredSkills((prev) =>
                            prev.map((s, i) =>
                              i === idx ? { ...s, skill: e.target.value } : s
                            )
                          )
                        }
                        placeholder={t.positions.skillName}
                        className="flex-1 rounded-md border px-2 py-1.5 text-sm bg-background"
                      />
                      <select
                        value={sk.level}
                        onChange={(e) =>
                          setPreferredSkills((prev) =>
                            prev.map((s, i) =>
                              i === idx ? { ...s, level: e.target.value } : s
                            )
                          )
                        }
                        className="w-24 rounded-md border px-2 py-1.5 text-sm bg-background"
                      >
                        {SKILL_LEVELS.map((lvl) => (
                          <option key={lvl} value={lvl}>
                            {t.positions[`level${lvl.charAt(0).toUpperCase() + lvl.slice(1)}` as keyof typeof t.positions] || lvl}
                          </option>
                        ))}
                      </select>
                      <button
                        type="button"
                        onClick={() =>
                          setPreferredSkills((prev) => prev.filter((_, i) => i !== idx))
                        }
                        className="text-red-400 hover:text-red-600 p-1"
                        title="Remove"
                      >
                        ×
                      </button>
                    </div>
                  ))}
                </div>
              )}
            </div>

            {/* Focus Areas */}
            <div>
              <label className="mb-1 block text-sm font-medium">{t.positions.focusAreasLabel}</label>
              <Input
                value={focusAreas}
                onChange={(e) => setFocusAreas(e.target.value)}
                placeholder={t.positions.focusAreasPlaceholder}
              />
            </div>

            {/* Questions + Duration */}
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="mb-1 block text-sm font-medium">{t.positions.defaultQuestions}</label>
                <Input
                  type="number"
                  min={1}
                  max={30}
                  value={defaultQuestions}
                  onChange={(e) => setDefaultQuestions(Number(e.target.value))}
                />
              </div>
              <div>
                <label className="mb-1 block text-sm font-medium">{t.positions.defaultDuration}</label>
                <Input
                  type="number"
                  min={5}
                  max={180}
                  value={defaultDuration}
                  onChange={(e) => setDefaultDuration(Number(e.target.value))}
                />
              </div>
            </div>

            {/* Soft Skills */}
            <div>
              <label className="mb-1 block text-sm font-medium">{t.positions.softSkillsLabel}</label>
              <div className="grid grid-cols-2 gap-2">
                {(["teamwork", "communication", "ownership", "leadership"] as const).map((key) => (
                  <div key={key} className="flex items-center gap-2">
                    <span className="text-xs w-20">{t.positions[key]}</span>
                    <select
                      value={softSkills[key]}
                      onChange={(e) =>
                        setSoftSkills((prev) => ({ ...prev, [key]: e.target.value }))
                      }
                      className="flex-1 rounded-md border px-2 py-1 text-xs bg-background"
                    >
                      {SOFT_SKILL_LEVELS.map((lvl) => (
                        <option key={lvl} value={lvl}>
                          {t.positions[`level${lvl.charAt(0).toUpperCase() + lvl.slice(1)}` as keyof typeof t.positions] || lvl}
                        </option>
                      ))}
                    </select>
                  </div>
                ))}
              </div>
            </div>

            {/* Submit */}
            <Button
              onClick={handleSave}
              disabled={saving || !title.trim()}
              className="w-full"
            >
              {saving
                ? (editingId ? t.positions.saving : t.positions.creating)
                : (editingId ? t.positions.save : t.positions.create)}
            </Button>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}
