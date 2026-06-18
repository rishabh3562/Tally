/**
 * Transaction List Component
 */

import { Transaction } from '../../types';

interface TransactionListProps {
  transactions: Transaction[];
  onSelect?: (transaction: Transaction) => void;
}

export default function TransactionList({ transactions }: TransactionListProps) {
  return (
    <div className="space-y-2">
      {/* TODO: Implement transaction list with filtering and sorting */}
      {transactions.length === 0 ? (
        <p className="text-gray-500">No transactions found</p>
      ) : (
        <ul className="space-y-1">
          {transactions.map((tx) => (
            <li key={tx.id} className="p-2 border rounded hover:bg-gray-50 cursor-pointer">
              {tx.raw_merchant} - {tx.amount}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
