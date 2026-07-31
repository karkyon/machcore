"use client";
// apps/web/components/shared/ApprovalModal.tsx
// [v094] MC/NC共通の承認モーダル。承認資格(canApprove=true)を持つユーザのみを
// 選択肢に表示し、そのユーザ自身のパスワードを都度検証して承認する
// (旧ACCESS「承認します」フォーム相当。編集中のログインセッションとは無関係)。
import { useState, useEffect } from "react";
import { usersApi, mcApi, ncApi, UserInfo } from "@/lib/api";
import { useLanguage } from "@/lib/i18n/LanguageContext";

type Props = {
  isOpen: boolean;
  system: "MC" | "NC";
  programId: number;
  onSuccess: () => void;
  onCancel: () => void;
};

export default function ApprovalModal({ isOpen, system, programId, onSuccess, onCancel }: Props) {
  const { t: tr } = useLanguage();
  const [approvers, setApprovers] = useState<UserInfo[]>([]);
  const [selected, setSelected] = useState<UserInfo | null>(null);
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [loadingList, setLoadingList] = useState(false);

  useEffect(() => {
    if (isOpen) {
      setSelected(null);
      setPassword("");
      setError(null);
      setLoadingList(true);
      usersApi.list(system, true)
        .then(r => setApprovers((r as any).data ?? r))
        .catch(() => setApprovers([]))
        .finally(() => setLoadingList(false));
    }
  }, [isOpen, system]);

  const handleSubmit = async () => {
    if (!selected || !password) return;
    setLoading(true);
    setError(null);
    try {
      if (system === "MC") {
        await mcApi.approve(programId, selected.id, password);
      } else {
        await ncApi.approve(programId, selected.id, password);
      }
      onSuccess();
    } catch (e: any) {
      const msg = e?.response?.data?.message ?? tr("approvalModal.approveFailedDefault","承認に失敗しました");
      setError(Array.isArray(msg) ? msg.join(", ") : msg);
      setPassword("");
    } finally {
      setLoading(false);
    }
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
      <div className="bg-white rounded-2xl shadow-2xl w-full max-w-md mx-4 overflow-hidden">
        <div className="bg-emerald-700 px-6 py-4">
          <h2 className="text-white font-bold text-lg">{tr("approvalModal.approveTitle", "承認する")}</h2>
          <p className="text-emerald-100 text-xs mt-1">
            {tr("approvalModal.approveDesc", "承認資格を持つ担当者を選択してパスワードを入力してください")}
          </p>
        </div>

        <div className="p-6 space-y-5">
          <div>
            <p className="text-xs font-bold text-slate-500 mb-2 uppercase tracking-wide">{tr("approvalModal.approverLabel5", "承認者")}</p>
            {loadingList ? (
              <p className="text-sm text-slate-400">{tr("approvalModal.loadingDots2b", "読み込み中...")}</p>
            ) : approvers.length === 0 ? (
              <p className="text-sm text-red-600 bg-red-50 rounded-lg px-3 py-2">
                {tr("approvalModal.noApproverUsers", "承認資格を持つユーザーが登録されていません。管理者にユーザ管理画面(承認資格)の設定を依頼してください。")}
              </p>
            ) : (
              <div className="grid grid-cols-3 gap-2 max-h-48 overflow-y-auto">
                {approvers.map(u => (
                  <button
                    key={u.id}
                    onClick={() => { setSelected(u); setError(null); }}
                    className={`px-3 py-2 rounded-lg text-sm font-medium border-2 transition-all ${
                      selected?.id === u.id
                        ? "border-emerald-500 bg-emerald-50 text-emerald-700"
                        : "border-slate-200 bg-white text-slate-700 hover:border-slate-300"
                    }`}
                  >
                    {u.name}
                  </button>
                ))}
              </div>
            )}
          </div>

          {selected && (
            <div>
              <p className="text-xs font-bold text-slate-500 mb-2 uppercase tracking-wide">
                {tr("approvalModal.passwordForLabel", "パスワード（{name}）").replace("{name}", selected.name)}
              </p>
              <input
                type="password"
                value={password}
                onChange={e => setPassword(e.target.value)}
                onKeyDown={e => e.key === "Enter" && handleSubmit()}
                autoFocus
                className="w-full border border-slate-300 rounded-lg px-4 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-emerald-400"
                placeholder={tr("approvalModal.passwordPlaceholder2", "パスワードを入力")}
              />
            </div>
          )}

          {error && (
            <p className="text-red-600 text-sm bg-red-50 rounded-lg px-4 py-2">{error}</p>
          )}

          <div className="flex gap-3 pt-2">
            <button
              onClick={onCancel}
              className="flex-1 px-4 py-2 rounded-lg border border-slate-300 text-slate-600 text-sm font-medium hover:bg-slate-50"
            >
              {tr("approvalModal.cancelButton10", "キャンセル")}
            </button>
            <button
              onClick={handleSubmit}
              disabled={!selected || !password || loading}
              className="flex-1 px-4 py-2 rounded-lg bg-emerald-600 text-white text-sm font-bold hover:bg-emerald-700 disabled:opacity-40 disabled:cursor-not-allowed"
            >
              {loading ? tr("approvalModal.approvingLabel", "承認中...") : tr("approvalModal.approveButton2", "承認する")}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
