"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import apiClient from "@/lib/api";
import { Plus, Trash2, Bank, CreditCard, DollarSign, Send } from "lucide-react";

type AccountType = "Bank" | "CreditCard" | "UPI" | "Investment";

interface Account {
  id: string;
  name: string;
  type: AccountType;
  bank_code?: string;
  created_at: string;
}

const ACCOUNT_TYPES: { value: AccountType; label: string; icon: React.ReactNode }[] = [
  { value: "Bank", label: "Bank Account", icon: <Bank className="w-5 h-5" /> },
  { value: "CreditCard", label: "Credit Card", icon: <CreditCard className="w-5 h-5" /> },
  { value: "UPI", label: "UPI Account", icon: <Send className="w-5 h-5" /> },
  { value: "Investment", label: "Investment", icon: <DollarSign className="w-5 h-5" /> },
];

const BANK_CODES = [
  { code: "HDFC", name: "HDFC Bank" },
  { code: "ICIC", name: "ICICI Bank" },
  { code: "AXIS", name: "Axis Bank" },
  { code: "SBIN", name: "State Bank of India" },
  { code: "KOTAK", name: "Kotak Bank" },
  { code: "YES", name: "YES Bank" },
  { code: "IDBI", name: "IDBI Bank" },
  { code: "INDUSIND", name: "IndusInd Bank" },
  { code: "OTHER", name: "Other Bank" },
];

export default function AccountsPage() {
  const queryClient = useQueryClient();
  const [showForm, setShowForm] = useState(false);
  const [formData, setFormData] = useState({
    name: "",
    type: "Bank" as AccountType,
    bank_code: "",
  });
  const [error, setError] = useState("");

  // Fetch accounts
  const { data: accountsData, isLoading } = useQuery({
    queryKey: ["accounts"],
    queryFn: async () => {
      const response = await apiClient.get("/api/accounts");
      return response.data || [];
    },
  });

  const accounts: Account[] = accountsData || [];

  // Create account mutation
  const createMutation = useMutation({
    mutationFn: async (newAccount: typeof formData) => {
      const response = await apiClient.post("/api/accounts", newAccount);
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["accounts"] });
      setFormData({ name: "", type: "Bank", bank_code: "" });
      setShowForm(false);
      setError("");
    },
    onError: (err: any) => {
      setError(err.response?.data?.detail || "Failed to create account");
    },
  });

  // Delete account mutation
  const deleteMutation = useMutation({
    mutationFn: async (accountId: string) => {
      await apiClient.delete(`/api/accounts/${accountId}`);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["accounts"] });
    },
  });

  const handleSubmit = (e) => {
    e.preventDefault();
    setError("");

    if (!formData.name.trim()) {
      setError("Account name is required");
      return;
    }

    if (!formData.type) {
      setError("Account type is required");
      return;
    }

    createMutation.mutate(formData);
  };

  const getAccountIcon = (type: AccountType) => {
    const typeConfig = ACCOUNT_TYPES.find((t) => t.value === type);
    return typeConfig?.icon || <Bank className="w-5 h-5" />;
  };

  const getBankName = (code?: string) => {
    if (!code) return "";
    return BANK_CODES.find((b) => b.code === code)?.name || code;
  };

  return (
    <div className="space-y-8">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-4xl font-bold text-gray-900">My Accounts</h1>
          <p className="text-gray-600 mt-1">Manage your bank accounts and financial profiles</p>
        </div>
        <button
          onClick={() => setShowForm(!showForm)}
          className="flex items-center gap-2 bg-blue-600 hover:bg-blue-700 text-white font-medium py-2 px-4 rounded-lg transition"
        >
          <Plus className="w-5 h-5" />
          Add Account
        </button>
      </div>

      {/* Add Account Form */}
      {showForm && (
        <div className="bg-white rounded-lg shadow p-6 border-l-4 border-blue-500">
          <h2 className="text-lg font-bold text-gray-900 mb-6">Create New Account</h2>

          {error && (
            <div className="mb-6 p-4 bg-red-50 border-l-4 border-red-500 rounded text-red-700 text-sm font-medium">
              ❌ {error}
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-6">
            {/* Account Name */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">Account Name</label>
              <input
                type="text"
                value={formData.name}
                onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                placeholder="e.g., My Savings Account"
                disabled={createMutation.isPending}
                className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent disabled:bg-gray-50"
              />
              <p className="text-xs text-gray-500 mt-1">Give your account a memorable name</p>
            </div>

            {/* Account Type */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-3">Account Type</label>
              <div className="grid grid-cols-2 gap-3">
                {ACCOUNT_TYPES.map((type) => (
                  <button
                    key={type.value}
                    type="button"
                    onClick={() => setFormData({ ...formData, type: type.value })}
                    disabled={createMutation.isPending}
                    className={`flex flex-col items-center gap-2 p-3 rounded-lg border-2 transition ${
                      formData.type === type.value
                        ? "border-blue-600 bg-blue-50"
                        : "border-gray-200 hover:border-gray-300"
                    } disabled:opacity-50`}
                  >
                    {type.icon}
                    <span className="text-sm font-medium text-gray-700">{type.label}</span>
                  </button>
                ))}
              </div>
            </div>

            {/* Bank Code */}
            {formData.type === "Bank" && (
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">Bank</label>
                <select
                  value={formData.bank_code}
                  onChange={(e) => setFormData({ ...formData, bank_code: e.target.value })}
                  disabled={createMutation.isPending}
                  className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent disabled:bg-gray-50"
                >
                  <option value="">Select your bank</option>
                  {BANK_CODES.map((bank) => (
                    <option key={bank.code} value={bank.code}>
                      {bank.name}
                    </option>
                  ))}
                </select>
              </div>
            )}

            {/* Buttons */}
            <div className="flex gap-3 pt-4">
              <button
                type="submit"
                disabled={createMutation.isPending}
                className="flex-1 bg-blue-600 hover:bg-blue-700 disabled:bg-gray-400 text-white font-medium py-2 rounded-lg transition"
              >
                {createMutation.isPending ? "Creating..." : "Create Account"}
              </button>
              <button
                type="button"
                onClick={() => {
                  setShowForm(false);
                  setError("");
                  setFormData({ name: "", type: "Bank", bank_code: "" });
                }}
                disabled={createMutation.isPending}
                className="flex-1 bg-gray-100 hover:bg-gray-200 text-gray-800 font-medium py-2 rounded-lg transition disabled:opacity-50"
              >
                Cancel
              </button>
            </div>
          </form>
        </div>
      )}

      {/* Accounts List */}
      <div>
        <h2 className="text-xl font-bold text-gray-900 mb-4">Your Accounts</h2>

        {isLoading ? (
          <div className="bg-white rounded-lg shadow p-8 text-center text-gray-600">
            Loading accounts...
          </div>
        ) : accounts.length === 0 ? (
          <div className="bg-blue-50 border border-blue-200 rounded-lg p-8 text-center">
            <Bank className="w-16 h-16 text-blue-400 mx-auto mb-4 opacity-50" />
            <p className="text-gray-600 font-medium mb-4">No accounts yet</p>
            <p className="text-gray-500 text-sm mb-6">Create your first account to start tracking transactions</p>
            <button
              onClick={() => setShowForm(true)}
              className="inline-flex items-center gap-2 bg-blue-600 hover:bg-blue-700 text-white font-medium py-2 px-6 rounded-lg transition"
            >
              <Plus className="w-5 h-5" />
              Create First Account
            </button>
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {accounts.map((account) => (
              <div key={account.id} className="bg-white rounded-lg shadow hover:shadow-md transition p-6 relative">
                {/* Delete Button */}
                <button
                  onClick={() => {
                    if (confirm(`Delete "${account.name}"?`)) {
                      deleteMutation.mutate(account.id);
                    }
                  }}
                  disabled={deleteMutation.isPending}
                  className="absolute top-4 right-4 text-red-600 hover:text-red-700 disabled:opacity-50"
                >
                  <Trash2 className="w-5 h-5" />
                </button>

                {/* Content */}
                <div className="space-y-4">
                  {/* Icon */}
                  <div className="w-12 h-12 bg-blue-100 rounded-lg flex items-center justify-center text-blue-600">
                    {getAccountIcon(account.type)}
                  </div>

                  {/* Account Name */}
                  <div>
                    <p className="text-sm text-gray-500">Account Name</p>
                    <p className="text-lg font-bold text-gray-900">{account.name}</p>
                  </div>

                  {/* Account Type */}
                  <div className="flex items-center justify-between">
                    <span className="text-sm text-gray-500">Type</span>
                    <span className="text-sm font-medium text-gray-900">{account.type}</span>
                  </div>

                  {/* Bank */}
                  {account.bank_code && (
                    <div className="flex items-center justify-between">
                      <span className="text-sm text-gray-500">Bank</span>
                      <span className="text-sm font-medium text-gray-900">{getBankName(account.bank_code)}</span>
                    </div>
                  )}

                  {/* Created */}
                  <div className="flex items-center justify-between text-xs text-gray-500">
                    <span>Created</span>
                    <span>{new Date(account.created_at).toLocaleDateString("en-IN")}</span>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
