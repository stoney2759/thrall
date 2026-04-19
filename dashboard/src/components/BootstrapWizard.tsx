// ============================================================
// BootstrapWizard.tsx
//
// Step 1: Human creation form (name + optional description)
// Step 2: Thrall review (informational only — COO is auto-created)
// Submit: Single POST /org/bootstrap call
// ============================================================

import React, { useState } from "react";
import { bootstrapOrg } from "../api/client";
import { useAppStore } from "../state/store";
import type { CreateHumanRequest } from "../api/types";

type WizardStep = "HUMAN" | "THRALL_REVIEW" | "SUBMITTING";

interface StepHumanFormProps {
  name: string;
  description: string;
  onChange: (field: "name" | "description", val: string) => void;
  onNext: () => void;
}

function StepHumanForm({ name, description, onChange, onNext }: StepHumanFormProps) {
  const valid = name.trim().length > 0;
  return (
    <div className="wiz-step">
      <div className="wiz-step-header">
        <span className="wiz-step-badge">01</span>
        <div>
          <h2>DEFINE HUMAN AUTHORITY</h2>
          <p>The Human node is the root of the org hierarchy. All authority descends from here.</p>
        </div>
      </div>
      <div className="form-field">
        <label htmlFor="human-name">HUMAN NAME <span className="required">*</span></label>
        <input
          id="human-name"
          type="text"
          value={name}
          onChange={(e) => onChange("name", e.target.value)}
          placeholder="e.g. Commander"
          autoFocus
          autoComplete="off"
        />
      </div>
      <div className="form-field">
        <label htmlFor="human-desc">DESCRIPTION <span className="optional">(optional)</span></label>
        <input
          id="human-desc"
          type="text"
          value={description}
          onChange={(e) => onChange("description", e.target.value)}
          placeholder="Role or context description"
          autoComplete="off"
        />
      </div>
      <div className="wiz-actions">
        <button className="btn-primary" onClick={onNext} disabled={!valid}>
          CONTINUE →
        </button>
      </div>
    </div>
  );
}

interface StepThrallReviewProps {
  humanName: string;
  onBack: () => void;
  onSubmit: () => void;
  submitting: boolean;
}

function StepThrallReview({ humanName, onBack, onSubmit, submitting }: StepThrallReviewProps) {
  return (
    <div className="wiz-step">
      <div className="wiz-step-header">
        <span className="wiz-step-badge">02</span>
        <div>
          <h2>THRALL AUTO-PROVISIONED</h2>
          <p>The Thrall (COO) node is automatically created by the backend kernel beneath the Human node. No additional input required.</p>
        </div>
      </div>
      <div className="review-card">
        <div className="review-row">
          <span className="review-label">HUMAN</span>
          <span className="review-value">{humanName}</span>
          <span className="review-badge human">ROOT</span>
        </div>
        <div className="review-connector">└──</div>
        <div className="review-row">
          <span className="review-label">THRALL (COO)</span>
          <span className="review-value">Auto-assigned by kernel</span>
          <span className="review-badge thrall">AUTO</span>
        </div>
      </div>
      <div className="review-notice">
        ⚠ Submitting this form initialises the org. This action cannot be undone from the UI.
      </div>
      <div className="wiz-actions">
        <button className="btn-ghost" onClick={onBack} disabled={submitting}>
          ← BACK
        </button>
        <button className="btn-primary" onClick={onSubmit} disabled={submitting}>
          {submitting ? "INITIALISING…" : "BOOTSTRAP ORG"}
        </button>
      </div>
    </div>
  );
}

export function BootstrapWizard({ onComplete }: { onComplete: () => void }) {
  const store = useAppStore();
  const [step, setStep] = useState<WizardStep>("HUMAN");
  const [humanName, setHumanName] = useState("");
  const [humanDesc, setHumanDesc] = useState("");
  const [error, setError] = useState<string | null>(null);

  const handleFieldChange = (field: "name" | "description", val: string) => {
    if (field === "name") setHumanName(val);
    else setHumanDesc(val);
  };

  const handleSubmit = async () => {
    setStep("SUBMITTING");
    setError(null);

    const body: CreateHumanRequest = {
      name: humanName.trim(),
      ...(humanDesc.trim() ? { description: humanDesc.trim() } : {}),
    };

    const result = await bootstrapOrg(body);

    if (!result.ok) {
      setError(result.error);
      setStep("THRALL_REVIEW");
      return;
    }

    const { human, coo, org } = result.data;
    store.setBootstrapped(human, coo, org.nodes);
    onComplete();
  };

  return (
    <div className="wizard-container">
      <div className="wizard-header">
        <div className="wizard-logo">OPENTHRALL</div>
        <div className="wizard-tagline">GOVERNANCE BOOTSTRAP SEQUENCE</div>
      </div>

      <div className="wizard-progress">
        <div className={`progress-step ${step !== "HUMAN" ? "done" : "active"}`}>
          <span>01</span> HUMAN
        </div>
        <div className="progress-line" />
        <div className={`progress-step ${step === "THRALL_REVIEW" || step === "SUBMITTING" ? "active" : ""}`}>
          <span>02</span> THRALL
        </div>
      </div>

      {error && (
        <div className="error-banner">
          <span className="error-icon">✕</span>
          <span>{error}</span>
          <button className="error-dismiss" onClick={() => setError(null)}>DISMISS</button>
        </div>
      )}

      {step === "HUMAN" && (
        <StepHumanForm
          name={humanName}
          description={humanDesc}
          onChange={handleFieldChange}
          onNext={() => setStep("THRALL_REVIEW")}
        />
      )}

      {(step === "THRALL_REVIEW" || step === "SUBMITTING") && (
        <StepThrallReview
          humanName={humanName}
          onBack={() => setStep("HUMAN")}
          onSubmit={handleSubmit}
          submitting={step === "SUBMITTING"}
        />
      )}
    </div>
  );
}
