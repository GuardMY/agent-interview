"use client";

import { useEffect, useRef, useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { useI18n } from "@/i18n";
import { getTemplates, listPositions, uploadResume } from "@/lib/api";
import { FileText, Plus, Upload, X } from "lucide-react";
import type { InterviewTemplate, JobPositionListItem } from "@/types";

interface CreateData {
  candidate_name: string;
  job_title: string;
  experience_level: string;
  key_skills: string[];
  interview_language: string;
  position_id?: string | null;
}

interface CreateResult {
  id: string;
  admin_token: string;
  candidate_token: string;
}

interface Props {
  onCreate: (data: CreateData) => Promise<CreateResult>;
  loading: boolean;
}

const LEVELS = [
  { key: "junior", labelKey: "levelJunior" as const },
  { key: "mid", labelKey: "levelMid" as const },
  { key: "senior", labelKey: "levelSenior" as const },
];

export function SessionCreateDialog({ onCreate, loading }: Props) {
  const { t } = useI18n();
  const [open, setOpen] = useState(false);
  const [name, setName] = useState("");
  const [job, setJob] = useState("");
  const [level, setLevel] = useState("mid");
  const [language, setLanguage] = useState("en");
  const [skills, setSkills] = useState("");
  const [positionId, setPositionId] = useState("");
  const [templates, setTemplates] = useState<InterviewTemplate[]>([]);
  const [positions, setPositions] = useState<JobPositionListItem[]>([]);
  const [resumeFile, setResumeFile] = useState<File | null>(null);
  const [uploading, setUploading] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    getTemplates().then(setTemplates).catch(() => {});
    // Load active positions for the selector
    listPositions({ status: "active", size: 100 })
      .then((res) => setPositions(res.items))
      .catch(() => {});
  }, []);

  const applyTemplate = (tpl: InterviewTemplate) => {
    setJob(tpl.job_title);
    setLevel(tpl.experience_level);
    setSkills(tpl.key_skills.join(", "));
  };

  const applyPosition = (posId: string) => {
    setPositionId(posId);
    const pos = positions.find((p) => p.id === posId);
    if (pos) {
      setJob(pos.title);
      setLevel(pos.level);
    }
  };

  const handleSubmit = async () => {
    if (!name.trim() || !job.trim()) return;
    const result = await onCreate({
      candidate_name: name.trim(),
      job_title: job.trim(),
      experience_level: level,
      key_skills: skills
        .split(",")
        .map((s) => s.trim())
        .filter(Boolean),
      interview_language: language,
      position_id: positionId || null,
    });
    // Upload resume if a file was selected
    if (resumeFile && result?.id && result?.admin_token) {
      setUploading(true);
      try {
        await uploadResume(result.id, resumeFile, result.admin_token);
      } catch {
        // Resume upload failure is non-fatal — session is already created
      } finally {
        setUploading(false);
      }
    }
    setName("");
    setJob("");
    setLevel("mid");
    setLanguage("en");
    setSkills("");
    setPositionId("");
    setResumeFile(null);
    setOpen(false);
  };

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger
        render={
          <Button>
            <Plus className="mr-2 h-4 w-4" />
            {t.dashboard.newSession}
          </Button>
        }
      />
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{t.session.createTitle}</DialogTitle>
        </DialogHeader>
        <div className="space-y-4 pt-2">
          {/* Template selector */}
          {templates.length > 0 && (
            <div>
              <label className="mb-1 block text-sm font-medium">
                {t.session.templateLabel}
              </label>
              <select
                onChange={(e) => {
                  const tpl = templates.find((t) => t.id === e.target.value);
                  if (tpl) applyTemplate(tpl);
                }}
                defaultValue=""
                className="w-full rounded-md border px-3 py-2 text-sm bg-background"
              >
                <option value="" disabled>
                  {t.session.templatePlaceholder}
                </option>
                {templates.map((tpl) => (
                  <option key={tpl.id} value={tpl.id}>
                    {tpl.name} ({tpl.experience_level})
                  </option>
                ))}
              </select>
            </div>
          )}

          {/* Position selector */}
          {positions.length > 0 && (
            <div>
              <label className="mb-1 block text-sm font-medium">
                {t.session.positionLabel}
              </label>
              <select
                value={positionId}
                onChange={(e) => applyPosition(e.target.value)}
                className="w-full rounded-md border px-3 py-2 text-sm bg-background"
              >
                <option value="">{t.session.positionPlaceholder}</option>
                {positions.map((pos) => (
                  <option key={pos.id} value={pos.id}>
                    {pos.title} ({t.session[LEVELS.find((l) => l.key === pos.level)?.labelKey || "levelMid"]}
                    {pos.department ? ` — ${pos.department}` : ""})
                  </option>
                ))}
              </select>
            </div>
          )}

          <div>
            <label className="mb-1 block text-sm font-medium">
              {t.session.candidateName}
            </label>
            <Input
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder={t.session.candidateNamePlaceholder}
            />
          </div>
          <div>
            <label className="mb-1 block text-sm font-medium">
              {t.session.jobTitle}
            </label>
            <Input
              value={job}
              onChange={(e) => setJob(e.target.value)}
              placeholder={t.session.jobTitlePlaceholder}
            />
          </div>
          <div>
            <label className="mb-1 block text-sm font-medium">
              {t.dashboard.experienceLevel}
            </label>
            <div className="flex gap-2">
              {LEVELS.map(({ key, labelKey }) => (
                <Button
                  key={key}
                  type="button"
                  variant={level === key ? "default" : "outline"}
                  size="sm"
                  onClick={() => setLevel(key)}
                  className="flex-1"
                >
                  {t.session[labelKey]}
                </Button>
              ))}
            </div>
          </div>
          <div>
            <label className="mb-1 block text-sm font-medium">
              {t.dashboard.interviewLanguage}
            </label>
            <div className="flex gap-2">
              {[
                { key: "en", label: "English" },
                { key: "zh", label: "中文" },
              ].map(({ key, label }) => (
                <Button
                  key={key}
                  type="button"
                  variant={language === key ? "default" : "outline"}
                  size="sm"
                  onClick={() => setLanguage(key)}
                  className="flex-1"
                >
                  {label}
                </Button>
              ))}
            </div>
          </div>
          <div>
            <label className="mb-1 block text-sm font-medium">
              {t.dashboard.keySkills}
            </label>
            <Input
              value={skills}
              onChange={(e) => setSkills(e.target.value)}
              placeholder={t.dashboard.keySkillsPlaceholder}
            />
          </div>

          {/* Resume upload */}
          <div>
            <label className="mb-1 block text-sm font-medium">简历上传（可选）</label>
            <input
              ref={fileInputRef}
              type="file"
              accept=".pdf,.docx,.txt"
              onChange={(e) => {
                const file = e.target.files?.[0] || null;
                setResumeFile(file);
              }}
              className="hidden"
            />
            {resumeFile ? (
              <div className="flex items-center gap-2 rounded-md border px-3 py-2 text-sm bg-muted/30">
                <FileText className="h-4 w-4 text-muted-foreground shrink-0" />
                <span className="flex-1 truncate">{resumeFile.name}</span>
                <span className="text-xs text-muted-foreground">
                  {(resumeFile.size / 1024).toFixed(0)} KB
                </span>
                <button
                  type="button"
                  onClick={() => {
                    setResumeFile(null);
                    if (fileInputRef.current) fileInputRef.current.value = "";
                  }}
                  className="text-muted-foreground hover:text-red-500 p-0.5"
                >
                  <X className="h-4 w-4" />
                </button>
              </div>
            ) : (
              <button
                type="button"
                onClick={() => fileInputRef.current?.click()}
                className="w-full flex items-center justify-center gap-2 rounded-md border border-dashed px-3 py-4 text-sm text-muted-foreground hover:border-primary hover:text-primary transition-colors"
              >
                <Upload className="h-4 w-4" />
                <span>点击上传简历（PDF / DOCX / TXT，≤ 5MB）</span>
              </button>
            )}
          </div>

          <Button
            onClick={handleSubmit}
            disabled={loading || uploading || !name.trim() || !job.trim()}
            className="w-full"
          >
            {uploading ? "上传简历中..." : loading ? t.session.creating : t.session.create}
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}
