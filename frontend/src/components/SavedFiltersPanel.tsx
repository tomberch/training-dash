import type { JSX } from "react";
import { useState, useEffect, useCallback } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from "@/components/ui/dialog";
import { cn } from "@/lib/utils";
import {
  fetchSavedFilters,
  createSavedFilter,
  updateSavedFilter,
  deleteSavedFilter,
  setDefaultFilter,
  clearDefaultFilter,
  type SavedFilter,
  ApiError,
  QueryError,
} from "../api";
import { toast } from "sonner";

// === Icons ===

function StarIcon({ filled = false }: { filled?: boolean }) {
  return (
    <svg
      className={cn("w-4 h-4", filled ? "fill-current text-warning" : "")}
      fill={filled ? "currentColor" : "none"}
      stroke="currentColor"
      viewBox="0 0 24 24"
    >
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeWidth={2}
        d="M11.049 2.927c.3-.921 1.603-.921 1.902 0l1.519 4.674a1 1 0 00.95.69h4.915c.969 0 1.371 1.24.588 1.81l-3.976 2.888a1 1 0 00-.363 1.118l1.518 4.674c.3.922-.755 1.688-1.538 1.118l-3.976-2.888a1 1 0 00-1.176 0l-3.976 2.888c-.783.57-1.838-.197-1.538-1.118l1.518-4.674a1 1 0 00-.363-1.118l-3.976-2.888c-.784-.57-.38-1.81.588-1.81h4.914a1 1 0 00.951-.69l1.519-4.674z"
      />
    </svg>
  );
}

function TrashIcon() {
  return (
    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeWidth={2}
        d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"
      />
    </svg>
  );
}

function PencilIcon() {
  return (
    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeWidth={2}
        d="M15.232 5.232l3.536 3.536m-2.036-5.036a2.5 2.5 0 113.536 3.536L6.5 21.036H3v-3.572L16.732 3.732z"
      />
    </svg>
  );
}

function SaveIcon() {
  return (
    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeWidth={2}
        d="M8 7H5a2 2 0 00-2 2v9a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2h-3m-1 4l-3 3m0 0l-3-3m3 3V4"
      />
    </svg>
  );
}

function FolderOpenIcon() {
  return (
    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeWidth={2}
        d="M5 19a2 2 0 01-2-2V7a2 2 0 012-2h4l2 2h4a2 2 0 012 2v1M5 19h14a2 2 0 002-2v-5a2 2 0 00-2-2H9a2 2 0 00-2 2v5a2 2 0 01-2 2z"
      />
    </svg>
  );
}

function ChevronDownIcon() {
  return (
    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
    </svg>
  );
}

// === Types ===

export interface SavedFiltersPanelProps {
  currentQuery: string;
  onLoadFilter: (query: string) => void;
}

// === Save Dialog ===

interface SaveDialogProps {
  open: boolean;
  onClose: () => void;
  currentQuery: string;
  existingFilter?: SavedFilter | null;
  onSaved: () => void;
}

function SaveDialog({ open, onClose, currentQuery, existingFilter, onSaved }: SaveDialogProps) {
  const [name, setName] = useState(existingFilter?.name || "");
  const [description, setDescription] = useState(existingFilter?.description || "");
  const [isDefault, setIsDefault] = useState(existingFilter?.is_default || false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (open) {
      setName(existingFilter?.name || "");
      setDescription(existingFilter?.description || "");
      setIsDefault(existingFilter?.is_default || false);
      setError(null);
    }
  }, [open, existingFilter]);

  const handleSave = async () => {
    if (!name.trim()) {
      setError("Name is required");
      return;
    }

    setSaving(true);
    setError(null);

    try {
      if (existingFilter) {
        await updateSavedFilter(existingFilter.id, {
          name: name.trim(),
          query_text: currentQuery,
          description: description.trim() || null,
          is_default: isDefault,
        });
        toast.success("Filter updated");
      } else {
        await createSavedFilter({
          name: name.trim(),
          query_text: currentQuery,
          description: description.trim() || null,
          is_default: isDefault,
        });
        toast.success("Filter saved");
      }
      onSaved();
      onClose();
    } catch (err) {
      if (err instanceof QueryError) {
        setError(`Query error: ${err.detail.message}`);
      } else if (err instanceof ApiError) {
        setError(err.message);
      } else {
        setError("Failed to save filter");
      }
    } finally {
      setSaving(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={(isOpen) => !isOpen && onClose()}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{existingFilter ? "Update Filter" : "Save Filter"}</DialogTitle>
          <DialogDescription>
            {existingFilter
              ? "Update your saved filter with the current query."
              : "Save the current query for quick access later."}
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4 py-4">
          <div className="space-y-1.5">
            <Label htmlFor="filter-name">Name</Label>
            <Input
              id="filter-name"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="e.g., High TSS rides"
              maxLength={100}
            />
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="filter-description">Description (optional)</Label>
            <Input
              id="filter-description"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="e.g., Rides with TSS > 100"
              maxLength={500}
            />
          </div>

          <div className="space-y-1.5">
            <Label>Query</Label>
            <div className="p-2 bg-muted rounded text-sm font-mono text-foreground overflow-x-auto">
              {currentQuery || <span className="text-muted-foreground">No query</span>}
            </div>
          </div>

          <label className="flex items-center gap-2 cursor-pointer">
            <input
              type="checkbox"
              checked={isDefault}
              onChange={(e) => setIsDefault(e.target.checked)}
              className="rounded border-border"
            />
            <span className="text-sm text-foreground">Set as default filter</span>
          </label>

          {error && (
            <div className="p-3 rounded-lg bg-destructive/10 text-destructive text-sm">
              {error}
            </div>
          )}
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={onClose} disabled={saving}>
            Cancel
          </Button>
          <Button onClick={handleSave} disabled={saving || !currentQuery}>
            {saving ? "Saving..." : existingFilter ? "Update" : "Save"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

// === Delete Confirmation Dialog ===

interface DeleteDialogProps {
  open: boolean;
  onClose: () => void;
  filter: SavedFilter | null;
  onDeleted: () => void;
}

function DeleteDialog({ open, onClose, filter, onDeleted }: DeleteDialogProps) {
  const [deleting, setDeleting] = useState(false);

  const handleDelete = async () => {
    if (!filter) return;

    setDeleting(true);
    try {
      await deleteSavedFilter(filter.id);
      toast.success("Filter deleted");
      onDeleted();
      onClose();
    } catch (err) {
      toast.error("Failed to delete filter");
    } finally {
      setDeleting(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={(isOpen) => !isOpen && onClose()}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Delete Filter</DialogTitle>
          <DialogDescription>
            Are you sure you want to delete "{filter?.name}"? This action cannot be undone.
          </DialogDescription>
        </DialogHeader>

        <DialogFooter>
          <Button variant="outline" onClick={onClose} disabled={deleting}>
            Cancel
          </Button>
          <Button variant="destructive" onClick={handleDelete} disabled={deleting}>
            {deleting ? "Deleting..." : "Delete"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

// === Filters List Dropdown ===

interface FiltersDropdownProps {
  filters: SavedFilter[];
  loading: boolean;
  onSelect: (filter: SavedFilter) => void;
  onEdit: (filter: SavedFilter) => void;
  onDelete: (filter: SavedFilter) => void;
  onToggleDefault: (filter: SavedFilter) => void;
}

function FiltersDropdown({
  filters,
  loading,
  onSelect,
  onEdit,
  onDelete,
  onToggleDefault,
}: FiltersDropdownProps) {
  const [open, setOpen] = useState(false);

  if (loading) {
    return (
      <Button variant="outline" size="sm" disabled className="gap-2">
        <FolderOpenIcon />
        Loading...
      </Button>
    );
  }

  return (
    <div className="relative">
      <Button
        variant="outline"
        size="sm"
        onClick={() => setOpen(!open)}
        className="gap-2"
      >
        <FolderOpenIcon />
        Saved Filters
        {filters.length > 0 && (
          <span className="ml-1 px-1.5 py-0.5 text-xs bg-muted rounded-full">
            {filters.length}
          </span>
        )}
        <ChevronDownIcon />
      </Button>

      {open && (
        <>
          {/* Backdrop */}
          <div
            className="fixed inset-0 z-40"
            onClick={() => setOpen(false)}
          />

          {/* Dropdown */}
          <div className="absolute top-full left-0 mt-1 w-80 bg-card border border-border rounded-lg shadow-lg z-50 overflow-hidden">
            {filters.length === 0 ? (
              <div className="p-4 text-center text-muted-foreground text-sm">
                No saved filters yet
              </div>
            ) : (
              <div className="max-h-80 overflow-y-auto">
                {filters.map((filter) => (
                  <div
                    key={filter.id}
                    className="flex items-center gap-2 p-3 hover:bg-muted/50 border-b border-border last:border-0"
                  >
                    <button
                      type="button"
                      className="flex-1 text-left min-w-0"
                      onClick={() => {
                        onSelect(filter);
                        setOpen(false);
                      }}
                    >
                      <div className="flex items-center gap-2">
                        <span className="font-medium text-foreground truncate">
                          {filter.name}
                        </span>
                        {filter.is_default && (
                          <span className="shrink-0">
                            <StarIcon filled />
                          </span>
                        )}
                      </div>
                      {filter.description && (
                        <p className="text-xs text-muted-foreground truncate mt-0.5">
                          {filter.description}
                        </p>
                      )}
                    </button>

                    {/* Actions */}
                    <div className="flex items-center gap-1 shrink-0">
                      <button
                        type="button"
                        onClick={(e) => {
                          e.stopPropagation();
                          onToggleDefault(filter);
                        }}
                        className="p-1.5 rounded hover:bg-muted text-muted-foreground hover:text-foreground"
                        title={filter.is_default ? "Remove default" : "Set as default"}
                      >
                        <StarIcon filled={filter.is_default} />
                      </button>
                      <button
                        type="button"
                        onClick={(e) => {
                          e.stopPropagation();
                          onEdit(filter);
                          setOpen(false);
                        }}
                        className="p-1.5 rounded hover:bg-muted text-muted-foreground hover:text-foreground"
                        title="Edit"
                      >
                        <PencilIcon />
                      </button>
                      <button
                        type="button"
                        onClick={(e) => {
                          e.stopPropagation();
                          onDelete(filter);
                          setOpen(false);
                        }}
                        className="p-1.5 rounded hover:bg-muted text-muted-foreground hover:text-destructive"
                        title="Delete"
                      >
                        <TrashIcon />
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </>
      )}
    </div>
  );
}

// === Main Component ===

export function SavedFiltersPanel({ currentQuery, onLoadFilter }: SavedFiltersPanelProps): JSX.Element {
  const [filters, setFilters] = useState<SavedFilter[]>([]);
  const [loading, setLoading] = useState(true);
  const [saveDialogOpen, setSaveDialogOpen] = useState(false);
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [editingFilter, setEditingFilter] = useState<SavedFilter | null>(null);
  const [filterToDelete, setFilterToDelete] = useState<SavedFilter | null>(null);

  const loadFilters = useCallback(async () => {
    try {
      const data = await fetchSavedFilters();
      setFilters(data);
    } catch (err) {
      console.error("Failed to load saved filters:", err);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadFilters();
  }, [loadFilters]);

  const handleSelect = (filter: SavedFilter) => {
    onLoadFilter(filter.query_text);
  };

  const handleEdit = (filter: SavedFilter) => {
    setEditingFilter(filter);
    setSaveDialogOpen(true);
  };

  const handleDelete = (filter: SavedFilter) => {
    setFilterToDelete(filter);
    setDeleteDialogOpen(true);
  };

  const handleToggleDefault = async (filter: SavedFilter) => {
    try {
      if (filter.is_default) {
        await clearDefaultFilter();
        toast.success("Default filter cleared");
      } else {
        await setDefaultFilter(filter.id);
        toast.success(`"${filter.name}" set as default`);
      }
      await loadFilters();
    } catch (err) {
      toast.error("Failed to update default filter");
    }
  };

  const handleSaveNew = () => {
    setEditingFilter(null);
    setSaveDialogOpen(true);
  };

  return (
    <div className="flex items-center gap-2">
      <FiltersDropdown
        filters={filters}
        loading={loading}
        onSelect={handleSelect}
        onEdit={handleEdit}
        onDelete={handleDelete}
        onToggleDefault={handleToggleDefault}
      />

      <Button
        variant="outline"
        size="sm"
        onClick={handleSaveNew}
        disabled={!currentQuery.trim()}
        className="gap-2"
      >
        <SaveIcon />
        Save
      </Button>

      <SaveDialog
        open={saveDialogOpen}
        onClose={() => {
          setSaveDialogOpen(false);
          setEditingFilter(null);
        }}
        currentQuery={currentQuery}
        existingFilter={editingFilter}
        onSaved={loadFilters}
      />

      <DeleteDialog
        open={deleteDialogOpen}
        onClose={() => {
          setDeleteDialogOpen(false);
          setFilterToDelete(null);
        }}
        filter={filterToDelete}
        onDeleted={loadFilters}
      />
    </div>
  );
}
