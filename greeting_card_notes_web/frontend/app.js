const MOMENTS_MAP = {
    celebrate: [
        { value: "birthday", label: "Birthday" },
        { value: "graduation", label: "Graduation" },
        { value: "promotion", label: "Promotion" },
        { value: "new_business", label: "New Business" },
        { value: "publication", label: "Publication" },
        { value: "award_or_recognition", label: "Award or Recognition" },
        { value: "new_job", label: "New Job" },
        { value: "new_home", label: "New Home" },
        { value: "engagement", label: "Engagement" },
        { value: "pregnancy_announcement", label: "Pregnancy Announcement" },
        { value: "retirement", label: "Retirement" },
        { value: "wedding", label: "Wedding" },
        { value: "anniversary", label: "Anniversary" },
        { value: "new_baby", label: "New Baby" },
    ],
    thank: [
        { value: "thank_you", label: "General Thank-you" },
    ],
    comfort: [
        { value: "get_well", label: "Get Well" },
        { value: "condolences", label: "Condolences" },
    ],
};

let currentFlowStep = 1;
let accountMode = "signup";
let supabaseClient = null;
let accessToken = null;
let currentUser = null;
let noteRequestInFlight = false;
let currentUserIsStaff = false;
let selectedRating = null;
let sessionData = {
    note_id: null,
    output_id: null,
    original_note: "",
    current_note: "",
    refinements_used: 0,
    refinements_max: 2,
};

document.addEventListener("DOMContentLoaded", () => {
    updateSpecificMoments();
    initAuth();
});

async function readApiError(response) {
    const statusCode = response.status;
    const raw = await response.text();
    if (raw.trim().startsWith("<!DOCTYPE") || raw.trim().startsWith("<html")) {
        if (statusCode === 502 || statusCode === 504) {
            return "The server timed out before the note finished. Try again.";
        }
        return `The server returned an error page (HTTP ${statusCode}).`;
    }
    try {
        const parsed = JSON.parse(raw);
        const detail = parsed.detail || parsed.message || raw;
        return typeof detail === "string" ? detail : JSON.stringify(detail);
    } catch (error) {
        return (raw || "").slice(0, 200) || `HTTP ${statusCode}`;
    }
}

function authHeaders() {
    const headers = { "Content-Type": "application/json" };
    if (accessToken) {
        headers.Authorization = `Bearer ${accessToken}`;
    }
    return headers;
}

async function apiFetch(path, options = {}) {
    const response = await fetch(path, {
        ...options,
        headers: {
            ...authHeaders(),
            ...(options.headers || {}),
        },
    });
    if (response.status === 401) {
        accessToken = null;
        currentUser = null;
        renderAccountChrome();
        throw new Error("Sign in required.");
    }
    if (!response.ok) {
        throw new Error(await readApiError(response));
    }
    if (response.status === 204) {
        return null;
    }
    return response.json();
}

async function initAuth() {
    const message = document.getElementById("account-message");
    let config;
    try {
        config = await fetch("/api/config").then((response) => response.json());
    } catch (error) {
        if (message) {
            message.textContent = "The sign-in service did not respond.";
        }
        return;
    }
    if (!config.auth_configured || !window.supabase) {
        if (message) {
            message.textContent = "Sign-in is not configured yet. Add SUPABASE_ANON_KEY on the server, then redeploy.";
        }
        return;
    }
    supabaseClient = window.supabase.createClient(config.supabase_url, config.supabase_anon_key, {
        auth: {
            persistSession: true,
            autoRefreshToken: true,
            detectSessionInUrl: true,
        },
    });
    const { data } = await supabaseClient.auth.getSession();
    setSession(data.session);
    supabaseClient.auth.onAuthStateChange((_event, session) => {
        setSession(session);
    });
}

function setSession(session) {
    accessToken = session ? session.access_token : null;
    currentUser = session ? session.user : null;
    renderAccountChrome();
    if (currentUser) {
        loadYourNotes();
        refreshStaffAccess();
    } else {
        currentUserIsStaff = false;
        renderNotesList([]);
        renderAccountChrome();
    }
}

function renderAccountChrome() {
    const label = document.getElementById("account-label");
    const logout = document.getElementById("logout-btn");
    const signedIn = document.getElementById("account-signed-in");
    const form = document.getElementById("account-form");
    const emailSlot = document.getElementById("signed-in-email");
    if (currentUser) {
        label.textContent = currentUser.email || "Signed in";
        label.classList.remove("hidden");
        logout.classList.remove("hidden");
        document.getElementById("review-btn").classList.toggle("hidden", !currentUserIsStaff);
        if (signedIn) signedIn.classList.remove("hidden");
        if (form) form.classList.add("hidden");
        if (emailSlot) emailSlot.textContent = currentUser.email || "";
    } else {
        label.textContent = "";
        label.classList.add("hidden");
        logout.classList.add("hidden");
        document.getElementById("review-btn").classList.add("hidden");
        if (signedIn) signedIn.classList.add("hidden");
        if (form) form.classList.remove("hidden");
    }
}

function toggleAccountMode() {
    accountMode = accountMode === "signup" ? "signin" : "signup";
    const signingUp = accountMode === "signup";
    document.getElementById("account-intro").textContent = signingUp
        ? "Create an account so the note is saved to you. There is no note limit until payments exist."
        : "Sign in to write a note or open one you already saved.";
    document.getElementById("account-submit").textContent = signingUp ? "Create account" : "Sign in";
    document.getElementById("account-switch-label").textContent = signingUp
        ? "Already have an account? Sign in"
        : "New here? Create an account";
    document.getElementById("password-confirm-wrap").classList.toggle("hidden", !signingUp);
    document.getElementById("newsletter-wrap").classList.toggle("hidden", !signingUp);
    document.getElementById("flow-password").setAttribute("autocomplete", signingUp ? "new-password" : "current-password");
    document.getElementById("account-message").textContent = "";
}

async function submitAccount(event) {
    event.preventDefault();
    const message = document.getElementById("account-message");
    message.textContent = "";
    if (!supabaseClient) {
        message.textContent = "Sign-in is not configured yet. Add SUPABASE_ANON_KEY on the server, then redeploy.";
        return;
    }
    const email = document.getElementById("flow-email").value.trim();
    const password = document.getElementById("flow-password").value;
    if (!email.includes("@")) {
        message.textContent = "Enter a valid email address.";
        return;
    }
    if (password.length < 6) {
        message.textContent = "Use at least 6 characters for the password.";
        return;
    }
    if (accountMode === "signup") {
        const confirmPassword = document.getElementById("flow-password-confirm").value;
        if (confirmPassword !== password) {
            message.textContent = "Passwords do not match.";
            return;
        }
        const { data, error } = await supabaseClient.auth.signUp({
            email,
            password,
            options: {
                data: {
                    newsletter_consent: document.getElementById("flow-newsletter").checked,
                },
            },
        });
        if (error) {
            message.textContent = error.message;
            return;
        }
        if (!data.session) {
            if (accountMode === "signup") {
                toggleAccountMode();
            }
            document.getElementById("account-message").textContent = "Check your email to confirm the account, then sign in.";
            return;
        }
        setSession(data.session);
        nextStep(1);
        return;
    }
    const { data, error } = await supabaseClient.auth.signInWithPassword({ email, password });
    if (error) {
        message.textContent = error.message;
        return;
    }
    setSession(data.session);
    nextStep(1);
}

async function refreshStaffAccess() {
    try {
        const data = await apiFetch("/api/review/access");
        currentUserIsStaff = Boolean(data.staff);
    } catch (error) {
        currentUserIsStaff = false;
    }
    renderAccountChrome();
}

async function logOut() {
    if (supabaseClient) {
        await supabaseClient.auth.signOut();
    }
    accessToken = null;
    currentUser = null;
    currentUserIsStaff = false;
    sessionData = {
        note_id: null,
        output_id: null,
        original_note: "",
        current_note: "",
        refinements_used: 0,
        refinements_max: 2,
    };
    renderAccountChrome();
    renderNotesList([]);
    showView("home");
}

function momentLabel(category, moment) {
    const match = (MOMENTS_MAP[category] || []).find((item) => item.value === moment);
    return match ? match.label : (moment || "").replaceAll("_", " ");
}

function renderNotesList(notes) {
    const section = document.getElementById("your-notes");
    const box = document.getElementById("your-notes-list");
    if (!currentUser) {
        section.classList.add("hidden");
        box.replaceChildren();
        return;
    }
    section.classList.remove("hidden");
    box.replaceChildren();
    if (!notes.length) {
        const empty = document.createElement("p");
        empty.className = "text-sm text-editorial-muted";
        empty.textContent = "No notes yet.";
        box.appendChild(empty);
        return;
    }
    notes.forEach((note) => {
        const button = document.createElement("button");
        button.type = "button";
        button.className = "text-left border border-editorial-border p-5 hover:border-editorial-text transition-colors";
        const title = document.createElement("span");
        title.className = "block font-serif text-lg text-editorial-text";
        const statusSuffix = note.status === "failed" ? " — did not finish" : note.status === "draft" ? " — draft" : "";
        title.textContent = `${momentLabel(note.occasion_category, note.specific_moment)} for ${note.recipient_name}${statusSuffix}`;
        button.appendChild(title);
        if (note.preview) {
            const preview = document.createElement("span");
            preview.className = "block text-sm text-editorial-muted mt-2";
            preview.textContent = note.preview;
            button.appendChild(preview);
        }
        button.addEventListener("click", () => openSavedNote(note.id));
        box.appendChild(button);
    });
}

async function loadYourNotes() {
    if (!accessToken) {
        return;
    }
    try {
        const data = await apiFetch("/api/notes");
        renderNotesList(data.notes || []);
    } catch (error) {
        renderNotesList([]);
    }
}

function showView(viewId) {
    document.querySelectorAll(".app-view").forEach((view) => view.classList.remove("active"));
    const activeView = document.getElementById(`view-${viewId}`);
    if (activeView) {
        activeView.classList.add("active");
    }
    window.scrollTo({ top: 0, behavior: "smooth" });
}

function scrollToSection(sectionId) {
    setTimeout(() => {
        const element = document.getElementById(sectionId);
        if (element) {
            element.scrollIntoView({ behavior: "smooth", block: "start" });
        }
    }, 100);
}

function updateSpecificMoments() {
    const category = document.getElementById("flow-category").value;
    const momentSelect = document.getElementById("flow-moment");
    momentSelect.replaceChildren();
    (MOMENTS_MAP[category] || []).forEach((item) => {
        const option = document.createElement("option");
        option.value = item.value;
        option.textContent = item.label;
        momentSelect.appendChild(option);
    });
}

function formFields() {
    return {
        occasion_category: document.getElementById("flow-category").value,
        specific_moment: document.getElementById("flow-moment").value,
        recipient_name: document.getElementById("flow-recipient-name").value.trim(),
        relationship: document.getElementById("flow-relationship").value,
        relationship_closeness: document.getElementById("flow-closeness").value,
        known_context: document.getElementById("flow-context").value.trim(),
        sender_name: document.getElementById("flow-sender-name").value.trim(),
        user_override: document.getElementById("flow-override").value.trim(),
    };
}

function fillForm(inputs) {
    document.getElementById("flow-category").value = inputs.occasion_category || "celebrate";
    updateSpecificMoments();
    if (inputs.specific_moment) {
        document.getElementById("flow-moment").value = inputs.specific_moment;
    }
    document.getElementById("flow-relationship").value = inputs.relationship || "friend";
    document.getElementById("flow-closeness").value = inputs.relationship_closeness || "warm";
    document.getElementById("flow-recipient-name").value = inputs.recipient_name || "";
    document.getElementById("flow-sender-name").value = inputs.sender_name || "";
    document.getElementById("flow-context").value = inputs.known_context === "No specific details provided." ? "" : (inputs.known_context || "");
    document.getElementById("flow-override").value = inputs.user_override || "";
}

async function saveDraftFromForm() {
    const payload = formFields();
    if (!payload.known_context) {
        payload.known_context = "";
    }
    if (sessionData.note_id && (sessionData.status === "draft" || sessionData.status === "failed")) {
        const data = await apiFetch(`/api/notes/${sessionData.note_id}`, {
            method: "PATCH",
            body: JSON.stringify(payload),
        });
        sessionData.note_id = data.note_id;
        sessionData.status = data.status;
        return;
    }
    const data = await apiFetch("/api/notes/drafts", {
        method: "POST",
        body: JSON.stringify(payload),
    });
    sessionData.note_id = data.note_id;
    sessionData.status = data.status || "draft";
}

function startNoteFlow(preselectedCategory = null) {
    sessionData.note_id = null;
    sessionData.status = null;
    document.getElementById("flow-recipient-name").value = "";
    document.getElementById("flow-sender-name").value = "";
    document.getElementById("flow-context").value = "";
    document.getElementById("flow-override").value = "";
    currentFlowStep = currentUser ? 2 : 1;
    if (preselectedCategory) {
        document.getElementById("flow-category").value = preselectedCategory;
        updateSpecificMoments();
    }
    setupFlowStepUI();
    showView("flow");
}

function cancelFlow() {
    if (confirm("Leave this note? Anything you have not saved will be lost.")) {
        showView("home");
    }
}

function setupFlowStepUI() {
    document.getElementById("flow-step-1").classList.add("hidden");
    document.getElementById("flow-step-2").classList.add("hidden");
    document.getElementById("flow-step-3").classList.add("hidden");
    document.getElementById("flow-loading").classList.add("hidden");
    document.getElementById(`flow-step-${currentFlowStep}`).classList.remove("hidden");
    renderAccountChrome();

    document.getElementById("step-number").textContent = `Step ${currentFlowStep} of 3`;
    if (currentFlowStep === 1) {
        document.getElementById("step-title").textContent = "Your account";
    } else if (currentFlowStep === 2) {
        document.getElementById("step-title").textContent = "Who and why";
    } else {
        document.getElementById("step-title").textContent = "Tell us what is true";
    }
}

async function nextStep(step) {
    if (step === 1 && !currentUser) {
        document.getElementById("account-message").textContent = "Create an account or sign in to continue.";
        return;
    }
    if (step === 2 && !document.getElementById("flow-recipient-name").value.trim()) {
        alert("Please enter the recipient's name.");
        return;
    }
    if (step === 2) {
        try {
            await saveDraftFromForm();
        } catch (error) {
            alert(error.message);
            return;
        }
    }
    currentFlowStep = step + 1;
    setupFlowStepUI();
}

function prevStep(step) {
    currentFlowStep = step - 1;
    setupFlowStepUI();
}

function applyNotePayload(data, craftNotes) {
    sessionData = {
        note_id: data.note_id || data.id,
        output_id: data.output_id,
        original_note: data.original_note || data.final_note || data.current_note || "",
        current_note: data.final_note || data.current_note || "",
        refinements_used: data.refinements_used || 0,
        refinements_max: data.refinements_max || 2,
    };
    updateResultUI(sessionData.current_note, craftNotes, data.feedback);
}

async function generateNoteSubmit() {
    if (noteRequestInFlight) {
        return;
    }
    if (!currentUser) {
        currentFlowStep = 1;
        setupFlowStepUI();
        document.getElementById("account-message").textContent = "Create an account or sign in to continue.";
        return;
    }
    const context = document.getElementById("flow-context").value.trim();
    if (!context) {
        const proceed = confirm("Write a note without personal details? One real detail makes it more specific.");
        if (!proceed) {
            return;
        }
    }

    document.getElementById("flow-step-3").classList.add("hidden");
    document.getElementById("flow-loading").classList.remove("hidden");
    document.getElementById("step-number").textContent = "Almost there";
    document.getElementById("step-title").textContent = "Writing your note";
    noteRequestInFlight = true;

    const payload = formFields();
    payload.known_context = context || "No specific details provided.";
    if (sessionData.note_id) {
        payload.note_id = sessionData.note_id;
    }

    try {
        const data = await apiFetch("/api/notes/generate", {
            method: "POST",
            body: JSON.stringify(payload),
        });
        applyNotePayload(data, data.craft_notes);
        showView("result");
        loadYourNotes();
    } catch (error) {
        alert(error.message);
        currentFlowStep = 3;
        setupFlowStepUI();
    } finally {
        noteRequestInFlight = false;
    }
}

function updateResultUI(note, craftNotes, feedback) {
    document.getElementById("note-display-area").textContent = note;
    document.getElementById("note-editor").value = note;

    const craftBox = document.getElementById("craft-notes-box");
    craftBox.replaceChildren();
    if (craftNotes) {
        const bullets = craftNotes.split("\n").filter((line) => line.trim().length > 3);
        if (bullets.length) {
            bullets.forEach((bullet) => {
                const paragraph = document.createElement("p");
                paragraph.textContent = bullet.replace(/^[\s\-*]+/, "").trim();
                craftBox.appendChild(paragraph);
            });
        } else {
            const paragraph = document.createElement("p");
            paragraph.textContent = craftNotes;
            craftBox.appendChild(paragraph);
        }
    }

    const remaining = sessionData.refinements_max - sessionData.refinements_used;
    document.getElementById("refinement-badge").textContent = `${remaining} of ${sessionData.refinements_max} remaining`;
    document.querySelectorAll(".refinement-btn").forEach((button) => {
        button.toggleAttribute("disabled", remaining <= 0);
    });
    document.getElementById("custom-refine-box").classList.toggle("opacity-50", remaining <= 0);
    document.getElementById("custom-refinement-text").toggleAttribute("disabled", remaining <= 0);
    document.getElementById("restore-original-btn").classList.toggle("hidden", sessionData.refinements_used <= 0);

    selectedRating = feedback && feedback.rating ? feedback.rating : null;
    document.querySelectorAll(".rating-btn").forEach((button) => {
        const active = Number(button.dataset.rating) === selectedRating;
        button.classList.toggle("border-editorial-text", active);
        button.classList.toggle("bg-editorial-border/40", active);
    });
    document.getElementById("reason-tag").value = feedback && feedback.reason_tag ? feedback.reason_tag : "";
    document.getElementById("feedback-status").textContent = "";
}

async function applyRefinement(instruction) {
    if (noteRequestInFlight) {
        return;
    }
    if (sessionData.refinements_used >= sessionData.refinements_max) {
        alert("You've used both AI rewrites for this note.");
        return;
    }
    const noteDisplay = document.getElementById("note-display-area");
    noteDisplay.textContent = "Refining note...";
    noteRequestInFlight = true;
    try {
        const data = await apiFetch(`/api/notes/${sessionData.note_id}/refine`, {
            method: "POST",
            body: JSON.stringify({ refinement_instruction: instruction }),
        });
        applyNotePayload(data, `Note updated: ${instruction}`);
    } catch (error) {
        alert(error.message);
        noteDisplay.textContent = sessionData.current_note;
    } finally {
        noteRequestInFlight = false;
    }
}

function applyCustomRefinement() {
    const text = document.getElementById("custom-refinement-text").value.trim();
    if (!text) {
        alert("Type a change first.");
        return;
    }
    applyRefinement(text);
    document.getElementById("custom-refinement-text").value = "";
}

async function restoreOriginalDraft() {
    if (sessionData.current_note === sessionData.original_note) {
        return;
    }
    const proceed = confirm("Show the first generated note again? AI rewrites you already used still count.");
    if (!proceed) {
        return;
    }
    await saveEdit(sessionData.original_note, "Restored the first generated note.");
}

async function saveEdit(text, craftNotes) {
    if (noteRequestInFlight) {
        return;
    }
    noteRequestInFlight = true;
    try {
        const data = await apiFetch(`/api/notes/${sessionData.note_id}/edits`, {
            method: "POST",
            body: JSON.stringify({ content: text }),
        });
        applyNotePayload(data, craftNotes || "Saved your edit.");
        cancelManualEdit();
    } catch (error) {
        alert(error.message);
    } finally {
        noteRequestInFlight = false;
    }
}

async function copyNoteToClipboard() {
    try {
        await navigator.clipboard.writeText(sessionData.current_note);
    } catch (error) {
        alert(`Failed to copy text: ${error}`);
        return;
    }
    if (sessionData.output_id) {
        try {
            await apiFetch(`/api/outputs/${sessionData.output_id}/copied`, { method: "POST" });
        } catch (error) {
            // The copy already succeeded. Saving the timestamp can fail without blocking the person.
        }
    }
    alert("Note text copied.");
}

function startManualEdit() {
    document.getElementById("note-display-area").classList.add("hidden");
    document.getElementById("note-edit-area").classList.remove("hidden");
    document.getElementById("note-editor").focus();
}

function cancelManualEdit() {
    document.getElementById("note-edit-area").classList.add("hidden");
    document.getElementById("note-display-area").classList.remove("hidden");
}

function saveManualEdit() {
    const editedText = document.getElementById("note-editor").value.trim();
    if (!editedText) {
        alert("Note text cannot be empty.");
        return;
    }
    saveEdit(editedText, "Saved your edit.");
}

function downloadTextFile() {
    const blob = new Blob([sessionData.current_note], { type: "text/plain;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = "rooting-for-you-note.txt";
    document.body.appendChild(link);
    link.click();
    link.remove();
    URL.revokeObjectURL(url);
}

function selectRating(rating) {
    selectedRating = rating;
    document.querySelectorAll(".rating-btn").forEach((button) => {
        const active = Number(button.dataset.rating) === rating;
        button.classList.toggle("border-editorial-text", active);
        button.classList.toggle("bg-editorial-border/40", active);
    });
}

async function submitFeedback() {
    const reason = document.getElementById("reason-tag").value;
    const status = document.getElementById("feedback-status");
    if (!selectedRating && !reason) {
        status.textContent = "Choose a rating or a reason.";
        return;
    }
    if (!sessionData.output_id) {
        status.textContent = "This note has no saved version yet.";
        return;
    }
    try {
        await apiFetch(`/api/outputs/${sessionData.output_id}/feedback`, {
            method: "POST",
            body: JSON.stringify({
                rating: selectedRating,
                reason_tag: reason || null,
            }),
        });
        status.textContent = "Saved.";
    } catch (error) {
        status.textContent = error.message;
    }
}

function resumeDraft(data) {
    fillForm(data.inputs || {});
    sessionData.note_id = data.id;
    sessionData.status = data.status;
    currentFlowStep = 3;
    setupFlowStepUI();
    showView("flow");
}

async function openSavedNote(noteId) {
    try {
        const data = await apiFetch(`/api/notes/${noteId}`);
        if (data.status === "draft" || (data.status === "failed" && !data.current_note)) {
            resumeDraft(data);
            return;
        }
        if (!data.current_note) {
            alert("This note is not ready yet.");
            return;
        }
        applyNotePayload({
            note_id: data.id,
            output_id: data.output_id,
            original_note: data.original_note,
            final_note: data.current_note,
            refinements_used: data.refinements_used,
            refinements_max: data.refinements_max,
            feedback: data.feedback,
        }, "");
        showView("result");
    } catch (error) {
        alert(error.message);
    }
}

async function openReview() {
    if (!currentUserIsStaff) {
        return;
    }
    showView("review");
    const list = document.getElementById("review-list");
    const detail = document.getElementById("review-detail");
    detail.classList.add("hidden");
    detail.replaceChildren();
    list.textContent = "Loading...";
    try {
        const data = await apiFetch("/api/review/notes");
        renderReviewList(data.notes || []);
    } catch (error) {
        list.textContent = error.message;
    }
}

function renderReviewList(notes) {
    const list = document.getElementById("review-list");
    list.replaceChildren();
    if (!notes.length) {
        const empty = document.createElement("p");
        empty.className = "text-sm text-editorial-muted";
        empty.textContent = "No notes to review.";
        list.appendChild(empty);
        return;
    }
    notes.forEach((note) => {
        const button = document.createElement("button");
        button.type = "button";
        button.className = "block w-full text-left border border-editorial-border p-4 hover:border-editorial-text";
        button.textContent = `${momentLabel(note.occasion_category, note.specific_moment)} for ${note.recipient_name}`;
        button.addEventListener("click", () => openReviewNote(note.id));
        list.appendChild(button);
    });
}

async function openReviewNote(noteId) {
    const detail = document.getElementById("review-detail");
    detail.classList.remove("hidden");
    detail.textContent = "Loading...";
    try {
        const data = await apiFetch(`/api/review/notes/${noteId}`);
        renderReviewDetail(data);
    } catch (error) {
        detail.textContent = error.message;
    }
}

function renderReviewDetail(data) {
    const detail = document.getElementById("review-detail");
    detail.replaceChildren();
    const finalVersion = (data.versions || []).find((version) => version.is_final) || (data.versions || []).at(-1);

    const context = document.createElement("p");
    context.className = "text-sm text-editorial-muted whitespace-pre-wrap";
    const inputs = data.inputs || {};
    context.textContent = [
        `${momentLabel(inputs.occasion_category, inputs.specific_moment)} for ${inputs.recipient_name || ""}`,
        inputs.relationship ? `Relationship: ${inputs.relationship}` : "",
        inputs.relationship_closeness ? `Closeness: ${inputs.relationship_closeness}` : "",
        inputs.known_context ? inputs.known_context : "",
    ].filter(Boolean).join("\n");
    detail.appendChild(context);

    const note = document.createElement("p");
    note.className = "font-serif text-lg italic whitespace-pre-wrap";
    note.textContent = finalVersion ? finalVersion.content : "No note text yet.";
    detail.appendChild(note);

    if (!finalVersion) {
        return;
    }

    const scoreLabel = document.createElement("label");
    scoreLabel.className = "block text-xs font-semibold uppercase tracking-wider";
    scoreLabel.textContent = "Staff score";
    scoreLabel.setAttribute("for", "qa-score");
    const score = document.createElement("select");
    score.id = "qa-score";
    score.className = "mt-2 w-full border border-editorial-border bg-editorial-bg px-3 py-2 text-sm";
    const emptyScore = document.createElement("option");
    emptyScore.value = "";
    emptyScore.textContent = "No score";
    score.appendChild(emptyScore);
    for (let value = 1; value <= 5; value += 1) {
        const option = document.createElement("option");
        option.value = String(value);
        option.textContent = String(value);
        if (finalVersion.qa_score === value) {
            option.selected = true;
        }
        score.appendChild(option);
    }
    detail.appendChild(scoreLabel);
    detail.appendChild(score);

    const tags = ["strong", "too_generic", "too_sentimental", "wrong_tone", "missed_point", "invented_detail"];
    const selectedTags = new Set(finalVersion.qa_tags || []);
    tags.forEach((tag) => {
        const row = document.createElement("label");
        row.className = "flex items-center gap-2 text-sm text-editorial-muted";
        const box = document.createElement("input");
        box.type = "checkbox";
        box.value = tag;
        box.className = "qa-tag";
        box.checked = selectedTags.has(tag);
        row.appendChild(box);
        row.appendChild(document.createTextNode(tag.replaceAll("_", " ")));
        detail.appendChild(row);
    });

    const notesLabel = document.createElement("label");
    notesLabel.className = "block text-xs font-semibold uppercase tracking-wider";
    notesLabel.textContent = "Staff note";
    notesLabel.setAttribute("for", "qa-notes");
    const notes = document.createElement("textarea");
    notes.id = "qa-notes";
    notes.rows = 4;
    notes.className = "mt-2 w-full border border-editorial-border bg-editorial-bg px-3 py-2 text-sm";
    notes.value = finalVersion.qa_notes || "";
    detail.appendChild(notesLabel);
    detail.appendChild(notes);

    const save = document.createElement("button");
    save.type = "button";
    save.className = "bg-editorial-text text-editorial-bg px-4 py-2 text-xs font-semibold";
    save.textContent = "Save score";
    const status = document.createElement("p");
    status.id = "qa-status";
    status.className = "text-xs text-editorial-muted";
    save.addEventListener("click", () => saveStaffScore(finalVersion.id, status));
    detail.appendChild(save);
    detail.appendChild(status);
}

async function saveStaffScore(outputId, status) {
    const scoreValue = document.getElementById("qa-score").value;
    const tags = [...document.querySelectorAll(".qa-tag:checked")].map((box) => box.value);
    const notes = document.getElementById("qa-notes").value.trim();
    if (!scoreValue && !tags.length && !notes) {
        status.textContent = "Add a score, a tag, or a note.";
        return;
    }
    try {
        await apiFetch(`/api/review/outputs/${outputId}/qa`, {
            method: "POST",
            body: JSON.stringify({
                qa_score: scoreValue ? Number(scoreValue) : null,
                qa_tags: tags,
                qa_notes: notes,
            }),
        });
        status.textContent = "Saved.";
    } catch (error) {
        status.textContent = error.message;
    }
}

async function deleteCurrentNote() {
    if (!sessionData.note_id) {
        return;
    }
    if (!confirm("Delete this note from your account?")) {
        return;
    }
    try {
        await apiFetch(`/api/notes/${sessionData.note_id}`, { method: "DELETE" });
        sessionData.note_id = null;
        showView("home");
        loadYourNotes();
    } catch (error) {
        alert(error.message);
    }
}
