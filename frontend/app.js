const documentType = document.getElementById("documentType");
const fileInput = document.getElementById("fileInput");
const processButton = document.getElementById("processButton");

const fileInfo = document.getElementById("fileInfo");
const errorMessage = document.getElementById("errorMessage");
const loadingSection = document.getElementById("loadingSection");
const resultsSection = document.getElementById("resultsSection");

const apiStatus = document.getElementById("apiStatus");

const resultDocumentName = document.getElementById("resultDocumentName");
const resultDocumentType = document.getElementById("resultDocumentType");
const resultPageCount = document.getElementById("resultPageCount");
const resultOCR = document.getElementById("resultOCR");
const resultModel = document.getElementById("resultModel");
const resultDuration = document.getElementById("resultDuration");
const processingStatus = document.getElementById("processingStatus");

const fileValidation = document.getElementById("fileValidation");
const extractedData = document.getElementById("extractedData");
const financialValidations = document.getElementById("financialValidations");

const rawJson = document.getElementById("rawJson");
const copyJsonButton = document.getElementById("copyJsonButton");
const copyMessage = document.getElementById("copyMessage");

const uploadZone = document.getElementById("uploadZone");

let currentResult = null;


/* -------------------------------------------------------
   API health
------------------------------------------------------- */

async function checkApiHealth() {
    try {
        const response = await fetch("/api/v1/health");

        if (!response.ok) {
            throw new Error("API unavailable");
        }

        apiStatus.innerHTML = `
            <span class="status-dot" style="background: #3b8d5a;"></span>
            <span>API connected</span>
        `;
    } catch (error) {
        apiStatus.innerHTML = `
            <span class="status-dot" style="background: #b94a48;"></span>
            <span>API unavailable</span>
        `;
    }
}


/* -------------------------------------------------------
   File selection
------------------------------------------------------- */
fileInput.addEventListener("change", () => {
    handleSelectedFile(fileInput.files[0]);
});

function handleSelectedFile(file) {
    hideError();

    if (!file) {
        fileInfo.classList.add("hidden");
        return;
    }

    const sizeMB = file.size / (1024 * 1024);

    fileInfo.textContent =
        `${file.name} · ${sizeMB.toFixed(2)} MB`;

    fileInfo.classList.remove("hidden");
}

if (uploadZone) {
    ["dragenter", "dragover"].forEach(eventName => {
        uploadZone.addEventListener(eventName, event => {
            event.preventDefault();
            uploadZone.classList.add("drag-active");
        });
    });

    ["dragleave", "drop"].forEach(eventName => {
        uploadZone.addEventListener(eventName, event => {
            event.preventDefault();
            uploadZone.classList.remove("drag-active");
        });
    });

    uploadZone.addEventListener("drop", event => {
        const file = event.dataTransfer.files[0];

        if (!file) {
            return;
        }

        const dataTransfer = new DataTransfer();
        dataTransfer.items.add(file);
        fileInput.files = dataTransfer.files;

        handleSelectedFile(file);
    });
}

/* -------------------------------------------------------
   Process document
------------------------------------------------------- */

processButton.addEventListener("click", processDocument);

async function processDocument() {
    hideError();

    const file = fileInput.files[0];

    if (!file) {
        showError("Please select a document first.");
        return;
    }

    const allowedExtensions = [".pdf", ".jpg", ".jpeg", ".png"];

    const filename = file.name.toLowerCase();

    if (!allowedExtensions.some(ext => filename.endsWith(ext))) {
        showError("Only PDF, JPG, JPEG and PNG files are supported.");
        return;
    }

    if (file.size === 0) {
        showError("The selected file is empty.");
        return;
    }

    if (file.size > 10 * 1024 * 1024) {
        showError("The file exceeds the 10 MB size limit.");
        return;
    }

    const formData = new FormData();

    formData.append("file", file);
    formData.append("document_type", documentType.value);

    setLoading(true);

    try {
        const response = await fetch(
            "/api/v1/documents/process",
            {
                method: "POST",
                body: formData
            }
        );

        const data = await response.json();

        if (!response.ok) {
            throw new Error(
                data.detail || "Document processing failed."
            );
        }

        renderResults(data);
        await loadRecentDocuments();

    } catch (error) {
        showError(error.message || "Something went wrong.");
    } finally {
        setLoading(false);
    }
}


/* -------------------------------------------------------
   Render results
------------------------------------------------------- */

function renderResults(data) {
    resultsSection.classList.remove("hidden");

        renderRawJson(data);

    resultDocumentName.textContent =
        data.document_name || "-";

    resultDocumentType.textContent =
        formatDocumentType(data.document_type);

    const metadata = data.processing_metadata || {};

    resultPageCount.textContent =
        metadata.page_count ?? "-";

    resultOCR.textContent =
        metadata.ocr_used ? "Yes" : "No";

    resultModel.textContent =
        metadata.model_used || "-";

    resultDuration.textContent =
        metadata.duration_ms != null
            ? `${metadata.duration_ms} ms`
            : "-";

    renderProcessingStatus(data.processing_status);

    renderFileValidation(data.file_validation);

    renderExtractedData(
        data.extracted_data,
        data.document_type
    );

    renderFinancialValidations(
        data.financial_validations
    );

    resultsSection.scrollIntoView({
        behavior: "smooth",
        block: "start"
    });
}


/* -------------------------------------------------------
   Processing status
------------------------------------------------------- */

function renderProcessingStatus(status) {
    const normalized = (status || "").toUpperCase();

    processingStatus.textContent =
        normalized || "-";

    processingStatus.className =
        "status-badge";

    if (normalized === "SUCCESS") {
        processingStatus.classList.add("status-success");
    } else if (normalized === "PARTIAL") {
        processingStatus.classList.add("status-partial");
    } else if (normalized === "FAILED") {
        processingStatus.classList.add("status-failed");
    }
}


/* -------------------------------------------------------
   File validation
------------------------------------------------------- */

function renderFileValidation(validation) {
    if (!validation) {
        fileValidation.innerHTML =
            `<div class="empty-message">No validation information available.</div>`;
        return;
    }

    const status =
        String(validation.status || "").toUpperCase();

    const passed = status === "PASSED";

    const statusClass = passed
        ? "status-success"
        : "status-failed";

    const issues = validation.issues || [];

    let html = `
        <div class="validation-item">
            <div class="validation-top">
                <span class="validation-name">
                    File validation
                </span>

                <span class="status-badge ${statusClass}">
                    ${escapeHtml(status || "-")}
                </span>
            </div>
    `;

    if (issues.length > 0) {
        html += `
            <div class="validation-details">
                ${issues
                    .map(issue => `• ${escapeHtml(issue)}`)
                    .join("<br>")}
            </div>
        `;
    } else {
        html += `
            <div class="validation-details">
                File passed format, size and readability checks.
            </div>
        `;
    }

    html += `</div>`;

    fileValidation.innerHTML = html;
}


/* -------------------------------------------------------
   Extracted data
------------------------------------------------------- */

function renderExtractedData(data, type) {
    if (!data) {
        extractedData.innerHTML = `
            <div class="empty-message">
                No extracted data available.
            </div>
        `;
        return;
    }

    let html = "";

    if (type === "invoice") {
        html = renderInvoice(data);
    } else if (type === "balance_sheet") {
        html = renderBalanceSheet(data);
    } else if (type === "profit_and_loss") {
        html = renderProfitAndLoss(data);
    } else if (type === "cash_flow_statement") {
        html = renderCashFlow(data);
    } else {
        html = renderGenericData(data);
    }

    extractedData.innerHTML = html;
}


/* -------------------------------------------------------
   Invoice
------------------------------------------------------- */

function renderInvoice(data) {
    let html = `
        <div class="info-grid">

            ${infoItem("Vendor", getValue(data.vendor?.name))}
            ${infoItem("Buyer", getValue(data.buyer?.name))}
            ${infoItem("Invoice Number", getValue(data.invoice_number))}
            ${infoItem("Invoice Date", getValue(data.invoice_date))}
            ${infoItem("Currency", getValue(data.currency?.iso_code))}
            ${infoItem("Due Date", getValue(data.due_date))}
            ${infoItem("Subtotal", formatNumber(data.subtotal))}
            ${infoItem("Grand Total", formatNumber(data.grand_total))}
            ${infoItem("Amount Paid", formatNumber(data.amount_paid))}
            ${infoItem("Amount Due", formatNumber(data.amount_due))}

        </div>
    `;

    if (data.line_items?.length) {
        html += `
            <h3 style="margin: 25px 0 12px;">
                Line Items
            </h3>

            <div class="table-wrapper">
                <table class="data-table">
                    <thead>
                        <tr>
                            <th>Description</th>
                            <th>Qty</th>
                            <th>Unit</th>
                            <th>Unit Price</th>
                            <th>Tax %</th>
                            <th>Line Total</th>
                        </tr>
                    </thead>

                    <tbody>
                        ${data.line_items.map(item => `
                            <tr>
                                <td>${escapeHtml(item.description || "-")}</td>
                                <td>${formatNumber(item.quantity)}</td>
                                <td>${escapeHtml(item.unit || "-")}</td>
                                <td>${formatNumber(item.unit_price)}</td>
                                <td>${formatNumber(item.tax_rate_percent)}</td>
                                <td>${formatNumber(item.line_total)}</td>
                            </tr>
                        `).join("")}
                    </tbody>
                </table>
            </div>
        `;
    }

    return html;
}


/* -------------------------------------------------------
   Balance sheet
------------------------------------------------------- */

function renderBalanceSheet(data) {
    return renderStatementData(data);
}


/* -------------------------------------------------------
   Profit & Loss
------------------------------------------------------- */

function renderProfitAndLoss(data) {
    return renderStatementData(data);
}


/* -------------------------------------------------------
   Cash Flow
------------------------------------------------------- */

function renderCashFlow(data) {
    return renderStatementData(data);
}


/* -------------------------------------------------------
   Financial statement renderer
------------------------------------------------------- */

function renderStatementData(data) {
    const rows = [];

    flattenObject(data, "", rows);

    if (!rows.length) {
        return `
            <div class="empty-message">
                No extracted financial data available.
            </div>
        `;
    }

    return `
        <div class="table-wrapper">
            <table class="data-table">
                <thead>
                    <tr>
                        <th>Field</th>
                        <th>Value</th>
                    </tr>
                </thead>

                <tbody>
                    ${rows.map(row => `
                        <tr>
                            <td>${escapeHtml(row.key)}</td>
                            <td>${escapeHtml(formatValue(row.value))}</td>
                        </tr>
                    `).join("")}
                </tbody>
            </table>
        </div>
    `;
}


/* -------------------------------------------------------
   Generic fallback
------------------------------------------------------- */

function renderGenericData(data) {
    const rows = [];

    flattenObject(data, "", rows);

    return `
        <div class="table-wrapper">
            <table class="data-table">
                <thead>
                    <tr>
                        <th>Field</th>
                        <th>Value</th>
                    </tr>
                </thead>

                <tbody>
                    ${rows.map(row => `
                        <tr>
                            <td>${escapeHtml(row.key)}</td>
                            <td>${escapeHtml(formatValue(row.value))}</td>
                        </tr>
                    `).join("")}
                </tbody>
            </table>
        </div>
    `;
}


/* -------------------------------------------------------
   Financial validations
------------------------------------------------------- */

function renderFinancialValidations(validations) {
    if (!validations || validations.length === 0) {
        financialValidations.innerHTML = `
            <div class="empty-message">
                No financial validations were applicable.
            </div>
        `;
        return;
    }

    financialValidations.innerHTML = `
        <div class="validation-list">

            ${validations.map(validation => {

                const status =
                    String(validation.status || "").toUpperCase();

                let statusClass = "validation-na";

                if (status === "PASS") {
                    statusClass = "validation-pass";
                } else if (status === "FAIL") {
                    statusClass = "validation-fail";
                }

                return `
                    <div class="validation-item">

                        <div class="validation-top">

                            <span class="validation-name">
                                ${escapeHtml(validation.name || "-")}
                            </span>

                            <strong class="${statusClass}">
                                ${escapeHtml(status || "-")}
                            </strong>

                        </div>

                        <div class="validation-details">

                            <strong>Formula:</strong>
                            ${escapeHtml(validation.formula || "-")}

                            <br>

                            <strong>Calculated:</strong>
                            ${formatNumber(validation.calculated)}

                            &nbsp;&nbsp;

                            <strong>Reported:</strong>
                            ${formatNumber(validation.reported)}

                            &nbsp;&nbsp;

                            <strong>Variance:</strong>
                            ${formatNumber(validation.variance)}

                            <br>

                            <strong>Reason:</strong>
                            ${escapeHtml(validation.reason || "-")}

                            ${validation.period
                                ? `<br><strong>Period:</strong> ${escapeHtml(validation.period)}`
                                : ""
                            }

                        </div>

                    </div>
                `;

            }).join("")}

        </div>
    `;
}


/* -------------------------------------------------------
   Helpers
------------------------------------------------------- */

function infoItem(label, value) {
    return `
        <div class="info-item">
            <span class="info-label">${escapeHtml(label)}</span>
            <span class="info-value">${escapeHtml(value ?? "-")}</span>
        </div>
    `;
}


function getValue(field) {
    if (field == null) {
        return null;
    }

    if (typeof field === "object" && "value" in field) {
        return field.value;
    }

    return field;
}


function formatNumber(value) {
    if (value === null || value === undefined || value === "") {
        return "-";
    }

    if (typeof value === "number") {
        return value.toLocaleString(
            "en-IN",
            {
                maximumFractionDigits: 4
            }
        );
    }

    return String(value);
}


function formatValue(value) {
    if (value === null || value === undefined) {
        return "-";
    }

    if (typeof value === "object") {
        if ("value" in value) {
            return formatValue(value.value);
        }

        return JSON.stringify(value);
    }

    return String(value);
}


function flattenObject(value, prefix, rows) {
    if (value === null || value === undefined) {
        if (prefix) {
            rows.push({
                key: prefix,
                value: null
            });
        }
        return;
    }

    if (Array.isArray(value)) {
        value.forEach((item, index) => {
            flattenObject(
                item,
                `${prefix} ${index + 1}`.trim(),
                rows
            );
        });
        return;
    }

    if (typeof value === "object") {
        Object.entries(value).forEach(([key, child]) => {

            if (key === "page" || key === "evidence") {
                return;
            }

            const nextPrefix = prefix
                ? `${prefix} / ${formatLabel(key)}`
                : formatLabel(key);

            if (
                child !== null &&
                typeof child === "object" &&
                !Array.isArray(child) &&
                "value" in child
            ) {
                rows.push({
                    key: nextPrefix,
                    value: child.value
                });
            } else {
                flattenObject(
                    child,
                    nextPrefix,
                    rows
                );
            }
        });

        return;
    }

    rows.push({
        key: prefix,
        value
    });
}


function formatLabel(value) {
    return String(value)
        .replace(/_/g, " ")
        .replace(/\b\w/g, char => char.toUpperCase());
}


function formatDocumentType(type) {
    const labels = {
        invoice: "Invoice",
        balance_sheet: "Balance Sheet",
        profit_and_loss: "Profit & Loss",
        cash_flow_statement: "Cash Flow"
    };

    return labels[type] || type || "-";
}


function escapeHtml(value) {
    if (value === null || value === undefined) {
        return "";
    }

    return String(value)
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#039;");
}


function setLoading(isLoading) {
    processButton.disabled = isLoading;

    loadingSection.classList.toggle(
        "hidden",
        !isLoading
    );

    if (isLoading) {
        resultsSection.classList.add("hidden");
    }
}


function showError(message) {
    errorMessage.textContent = message;
    errorMessage.classList.remove("hidden");
}


function hideError() {
    errorMessage.textContent = "";
    errorMessage.classList.add("hidden");
}

/* -------------------------------------------------------
   Recent documents dashboard
------------------------------------------------------- */

function createRecentDocumentsSection() {
    if (document.getElementById("recentDocumentsSection")) {
        return document.getElementById("recentDocumentsSection");
    }

    const section = document.createElement("section");

    section.id = "recentDocumentsSection";
    section.className = "card recent-documents-section";

    section.innerHTML = `
        <div class="section-title">
            <div>
                <p class="eyebrow">DOCUMENT HISTORY</p>
                <h2>Recent documents</h2>
                <p>Open a previously processed document and view its stored result.</p>
            </div>
        </div>

        <div id="recentDocuments">
            <div class="empty-message">
                Loading processed documents...
            </div>
        </div>
    `;

    if (resultsSection && resultsSection.parentNode) {
        resultsSection.parentNode.insertBefore(
            section,
            resultsSection
        );
    } else {
        document.querySelector("main")?.appendChild(section);
    }

    return section;
}


async function loadRecentDocuments() {
    const section = createRecentDocumentsSection();
    const container =
        document.getElementById("recentDocuments");

    if (!container) {
        return;
    }

    try {
        const response =
            await fetch("/api/v1/documents/");

        if (!response.ok) {
            throw new Error("Unable to load document history.");
        }

        const data = await response.json();

        const documents =
            Array.isArray(data)
                ? data
                : (
                    data.documents ||
                    data.items ||
                    []
                );

        renderRecentDocuments(documents);

    } catch (error) {
        container.innerHTML = `
            <div class="empty-message">
                Unable to load document history.
            </div>
        `;
    }
}


function renderRecentDocuments(documents) {
    const container =
        document.getElementById("recentDocuments");

    if (!container) {
        return;
    }

    if (!documents.length) {
        container.innerHTML = `
            <div class="empty-message">
                No documents have been processed yet.
            </div>
        `;
        return;
    }

    container.innerHTML = `
        <div class="table-wrapper">
            <table class="data-table">
                <thead>
                    <tr>
                        <th>Document</th>
                        <th>Type</th>
                        <th>Status</th>
                        <th>Processed</th>
                        <th></th>
                    </tr>
                </thead>

                <tbody>
                    ${documents.map(document => `
                        <tr>
                            <td>
                                <strong>
                                    ${escapeHtml(
                                        document.document_name || "-"
                                    )}
                                </strong>
                            </td>

                            <td>
                                ${escapeHtml(
                                    formatDocumentType(
                                        document.document_type
                                    )
                                )}
                            </td>

                            <td>
                                ${renderDashboardStatus(
                                    document.processing_status
                                )}
                            </td>

                            <td>
                                ${formatProcessedTime(
                                    document.processed_at
                                    || document.processing_metadata?.processed_at
                                )}
                            </td>

                            <td>
                                <button
                                    class="secondary-button document-open-button"
                                    data-document-name="${escapeHtml(
                                        document.document_name || ""
                                    )}"
                                >
                                    View result
                                </button>
                            </td>
                        </tr>
                    `).join("")}
                </tbody>
            </table>
        </div>
    `;

    container
        .querySelectorAll(".document-open-button")
        .forEach(button => {
            button.addEventListener("click", () => {
                loadStoredDocument(
                    button.dataset.documentName
                );
            });
        });
}


function renderDashboardStatus(status) {
    const normalized =
        String(status || "").toUpperCase();

    let statusClass = "status-badge";

    if (normalized === "SUCCESS") {
        statusClass += " status-success";
    } else if (normalized === "PARTIAL") {
        statusClass += " status-partial";
    } else if (normalized === "FAILED") {
        statusClass += " status-failed";
    }

    return `
        <span class="${statusClass}">
            ${escapeHtml(normalized || "-")}
        </span>
    `;
}


function formatProcessedTime(value) {
    if (!value) {
        return "-";
    }

    const date = new Date(value);

    if (Number.isNaN(date.getTime())) {
        return escapeHtml(String(value));
    }

    return escapeHtml(
        date.toLocaleString("en-IN", {
            dateStyle: "medium",
            timeStyle: "short"
        })
    );
}


async function loadStoredDocument(documentName) {
    if (!documentName) {
        return;
    }

    hideError();
    setLoading(true);

    try {
        const response = await fetch(
            `/api/v1/documents/${encodeURIComponent(documentName)}`
        );

        const data = await response.json();

        if (!response.ok) {
            throw new Error(
                data.detail ||
                "Unable to load the stored document."
            );
        }

        renderResults(data);

    } catch (error) {
        showError(
            error.message ||
            "Unable to load the stored document."
        );
    } finally {
        setLoading(false);
    }
}

/* -------------------------------------------------------
   Raw JSON viewer
------------------------------------------------------- */

function renderRawJson(data) {
    currentResult = data;

    if (!rawJson) {
        return;
    }

    rawJson.textContent =
        JSON.stringify(data, null, 2);

    if (copyMessage) {
        copyMessage.textContent = "";
    }
}


if (copyJsonButton) {
    copyJsonButton.addEventListener(
        "click",
        async () => {
            if (!currentResult) {
                return;
            }

            try {
                await navigator.clipboard.writeText(
                    JSON.stringify(
                        currentResult,
                        null,
                        2
                    )
                );

                if (copyMessage) {
                    copyMessage.textContent =
                        "JSON copied to clipboard.";
                }

            } catch (error) {
                if (copyMessage) {
                    copyMessage.textContent =
                        "Unable to copy JSON.";
                }
            }
        }
    );
}

/* -------------------------------------------------------
   Start
------------------------------------------------------- */

checkApiHealth();
createRecentDocumentsSection();
loadRecentDocuments();