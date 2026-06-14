import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ChevronRight, FolderPlus, Pencil, Plus, Trash2 } from "lucide-react";
import { api, ApiError } from "@/lib/api";
import { useAuth } from "@/auth/AuthContext";
import { useToast } from "@/components/Toast";
import { Modal } from "@/components/Modal";
import { Button, Card, EmptyState, Input, Label, PageSpinner, Select } from "@/components/ui";
import type { LocationNode } from "@/lib/types";

const KINDS = ["room", "unit", "section", "custom"];

interface EditState {
  id?: number;
  parent_id: number | null;
  name: string;
  kind: string;
}

function flatten(nodes: LocationNode[], depth = 0): { id: number; label: string }[] {
  return nodes.flatMap((n) => [
    { id: n.id, label: `${"  ".repeat(depth)}${n.name}` },
    ...flatten(n.children, depth + 1),
  ]);
}

export function LocationsPage() {
  const { household } = useAuth();
  const hid = household?.id;
  const qc = useQueryClient();
  const toast = useToast();
  const [edit, setEdit] = useState<EditState | null>(null);

  const { data: tree, isLoading } = useQuery({
    queryKey: ["locations", hid],
    queryFn: () => api.get<LocationNode[]>(`/api/households/${hid}/locations`),
    enabled: !!hid,
  });

  const options = useMemo(() => (tree ? flatten(tree) : []), [tree]);

  const invalidate = () => {
    qc.invalidateQueries({ queryKey: ["locations", hid] });
    qc.invalidateQueries({ queryKey: ["search"] });
  };

  const saveMut = useMutation({
    mutationFn: async (state: EditState) => {
      if (state.id) {
        return api.patch(`/api/households/${hid}/locations/${state.id}`, {
          name: state.name,
          kind: state.kind,
          parent_id: state.parent_id,
        });
      }
      return api.post(`/api/households/${hid}/locations`, {
        name: state.name,
        kind: state.kind,
        parent_id: state.parent_id,
      });
    },
    onSuccess: () => {
      invalidate();
      setEdit(null);
    },
    onError: (e) => toast.push(e instanceof ApiError ? e.message : "Save failed", "error"),
  });

  const deleteMut = useMutation({
    mutationFn: (id: number) => api.del(`/api/households/${hid}/locations/${id}`),
    onSuccess: invalidate,
    onError: (e) => toast.push(e instanceof ApiError ? e.message : "Delete failed", "error"),
  });

  return (
    <div className="mx-auto max-w-2xl space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold">Locations</h1>
          <p className="text-sm text-muted-foreground">
            Build your own hierarchy, e.g. Office Shelf 1 / Section 3 / Left.
          </p>
        </div>
        <Button onClick={() => setEdit({ parent_id: null, name: "", kind: "room" })}>
          <FolderPlus className="h-4 w-4" /> Add
        </Button>
      </div>

      {isLoading ? (
        <PageSpinner />
      ) : !tree || tree.length === 0 ? (
        <EmptyState title="No locations yet" hint="Add a room or shelf to start organizing." />
      ) : (
        <Card className="p-2">
          <ul>
            {tree.map((node) => (
              <TreeRow
                key={node.id}
                node={node}
                depth={0}
                onAddChild={(parentId) =>
                  setEdit({ parent_id: parentId, name: "", kind: "section" })
                }
                onEdit={(n) =>
                  setEdit({ id: n.id, parent_id: n.parent_id, name: n.name, kind: n.kind })
                }
                onDelete={(id) => {
                  if (confirm("Delete this location and its sub-locations?")) deleteMut.mutate(id);
                }}
              />
            ))}
          </ul>
        </Card>
      )}

      <Modal
        open={!!edit}
        onClose={() => setEdit(null)}
        title={edit?.id ? "Edit location" : "New location"}
        footer={
          <>
            <Button variant="ghost" onClick={() => setEdit(null)}>
              Cancel
            </Button>
            <Button onClick={() => edit && saveMut.mutate(edit)} loading={saveMut.isPending}>
              Save
            </Button>
          </>
        }
      >
        {edit && (
          <div className="space-y-3">
            <div>
              <Label>Name</Label>
              <Input
                autoFocus
                value={edit.name}
                onChange={(e) => setEdit({ ...edit, name: e.target.value })}
                placeholder="e.g. Office Shelf 1"
              />
            </div>
            <div>
              <Label>Type</Label>
              <Select value={edit.kind} onChange={(e) => setEdit({ ...edit, kind: e.target.value })}>
                {KINDS.map((k) => (
                  <option key={k} value={k}>
                    {k}
                  </option>
                ))}
              </Select>
            </div>
            <div>
              <Label>Parent</Label>
              <Select
                value={edit.parent_id ?? ""}
                onChange={(e) =>
                  setEdit({ ...edit, parent_id: e.target.value ? Number(e.target.value) : null })
                }
              >
                <option value="">None (top level)</option>
                {options
                  .filter((o) => o.id !== edit.id)
                  .map((o) => (
                    <option key={o.id} value={o.id}>
                      {o.label}
                    </option>
                  ))}
              </Select>
            </div>
          </div>
        )}
      </Modal>
    </div>
  );
}

function TreeRow({
  node,
  depth,
  onAddChild,
  onEdit,
  onDelete,
}: {
  node: LocationNode;
  depth: number;
  onAddChild: (parentId: number) => void;
  onEdit: (n: LocationNode) => void;
  onDelete: (id: number) => void;
}) {
  return (
    <>
      <li
        className="group flex items-center gap-1 rounded-md py-1.5 pr-1 hover:bg-accent"
        style={{ paddingLeft: depth * 18 + 6 }}
      >
        <ChevronRight
          className={`h-3.5 w-3.5 text-muted-foreground ${node.children.length ? "" : "opacity-0"}`}
        />
        <span className="flex-1 text-sm">{node.name}</span>
        <span className="rounded bg-muted px-1.5 py-0.5 text-[10px] text-muted-foreground">
          {node.kind}
        </span>
        <div className="flex opacity-0 transition-opacity group-hover:opacity-100">
          <Button variant="ghost" size="icon" onClick={() => onAddChild(node.id)} aria-label="Add child">
            <Plus className="h-3.5 w-3.5" />
          </Button>
          <Button variant="ghost" size="icon" onClick={() => onEdit(node)} aria-label="Edit">
            <Pencil className="h-3.5 w-3.5" />
          </Button>
          <Button variant="ghost" size="icon" onClick={() => onDelete(node.id)} aria-label="Delete">
            <Trash2 className="h-3.5 w-3.5 text-destructive" />
          </Button>
        </div>
      </li>
      {node.children.map((c) => (
        <TreeRow
          key={c.id}
          node={c}
          depth={depth + 1}
          onAddChild={onAddChild}
          onEdit={onEdit}
          onDelete={onDelete}
        />
      ))}
    </>
  );
}
