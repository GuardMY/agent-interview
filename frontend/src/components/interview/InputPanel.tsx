"use client";

import { useState, useRef } from "react";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { useI18n } from "@/i18n";
import { SkipForward, RotateCcw, Send } from "lucide-react";

interface Props {
  onSend: (content: string) => void;
  onSkip: () => void;
  onRepeat: () => void;
  disabled: boolean;
  isQaActive: boolean;
}

export function InputPanel({
  onSend,
  onSkip,
  onRepeat,
  disabled,
  isQaActive,
}: Props) {
  const { t } = useI18n();
  const [value, setValue] = useState("");
  const inputRef = useRef<HTMLTextAreaElement>(null);

  const handleSend = () => {
    const trimmed = value.trim();
    if (!trimmed || disabled) return;
    onSend(trimmed);
    setValue("");
    inputRef.current?.focus();
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  return (
    <div className="border-t bg-white px-4 py-3">
      <div className="mx-auto flex max-w-3xl items-end gap-2">
        {isQaActive && (
          <div className="flex gap-1">
            <Button
              variant="outline"
              size="sm"
              onClick={onRepeat}
              disabled={disabled}
              title={t.interview.repeat}
            >
              <RotateCcw className="h-4 w-4" />
            </Button>
            <Button
              variant="outline"
              size="sm"
              onClick={onSkip}
              disabled={disabled}
              title={t.interview.skip}
            >
              <SkipForward className="h-4 w-4" />
            </Button>
          </div>
        )}

        <Textarea
          ref={inputRef}
          value={value}
          onChange={(e) => setValue(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder={t.interview.inputPlaceholder}
          disabled={disabled}
          className="min-h-[44px] flex-1 resize-none"
          rows={1}
          maxLength={5000}
        />

        <Button
          onClick={handleSend}
          disabled={disabled || !value.trim()}
          size="sm"
          className="h-11 px-4"
        >
          <Send className="h-4 w-4" />
        </Button>
      </div>

      <p className="mx-auto mt-1 max-w-3xl text-center text-[10px] text-gray-400">
        {t.interview.sendHint}
      </p>
    </div>
  );
}
