"use client";

import { useEffect, useState } from "react";
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
import { getTemplates } from "@/lib/api";
import { Plus } from "lucide-react";
import type { InterviewTemplate } from "@/types";

interface Props {
  onCreate: (data: {
    candidate_name: string;
    job_title: string;
    experience_level: string;
    key_skills: string[];
    interview_language: string;
  }) => void;
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
  const [templates, setTemplates] = useState<InterviewTemplate[]>([]);

  useEffect(() => {
    getTemplates().then(setTemplates).catch(() => {});
  }, []);

  const applyTemplate = (tpl: InterviewTemplate) => {
    setJob(tpl.job_title);
    setLevel(tpl.experience_level);
    setSkills(tpl.key_skills.join(", "));
  };

  const handleSubmit = () => {
    if (!name.trim() || !job.trim()) return;
    onCreate({
      candidate_name: name.trim(),
      job_title: job.trim(),
      experience_level: level,
      key_skills: skills
        .split(",")
        .map((s) => s.trim())
        .filter(Boolean),
      interview_language: language,
    });
    setName("");
    setJob("");
    setLevel("mid");
    setLanguage("en");
    setSkills("");
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
          <Button
            onClick={handleSubmit}
            disabled={loading || !name.trim() || !job.trim()}
            className="w-full"
          >
            {loading ? t.session.creating : t.session.create}
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}
