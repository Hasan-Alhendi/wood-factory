const FACTORY_STAGE_ROLES = {
    "Cutting": "Factory Cutting Operator",
    "Edge Banding": "Factory Edge Banding Operator",
    "Drilling": "Factory Drilling Operator",
    "Assembly": "Factory Assembly Operator",
    "Quality Inspection": "Factory Quality Inspector",
    "Packing": "Factory Packing Operator",
};
const FACTORY_MANAGEMENT_ROLES = ["System Manager", "Manufacturing Manager", "Factory Manager"];
const FACTORY_SUPERVISION_ROLES = [...FACTORY_MANAGEMENT_ROLES, "Factory Supervisor"];
const FACTORY_PLANNING_ROLES = [...FACTORY_SUPERVISION_ROLES, "Factory Planner"];
const FACTORY_FINANCE_ROLES = ["System Manager", "Manufacturing Manager", "Factory Manager", "Accounts Manager", "Factory Accountant"];
const FACTORY_DELIVERY_ROLES = [...FACTORY_SUPERVISION_ROLES, "Factory Delivery User"];

frappe.ui.form.on("Factory Order", {
    setup(frm) {
        frm.set_query("cost_center", () => ({filters: {company: frm.doc.company, is_group: 0}}));
        frm.set_query("rework_cost_center", () => ({filters: {company: frm.doc.company, is_group: 0}}));
        frm.set_query("project", () => ({filters: {company: frm.doc.company}}));
    },
    refresh(frm) {
        const canPlan = has_any_role(FACTORY_PLANNING_ROLES);
        const canFinance = has_any_role(FACTORY_FINANCE_ROLES);
        const canDeliver = has_any_role(FACTORY_DELIVERY_ROLES);

        if (!frm.is_new() && !(frm.doc.production_stages || []).length && canPlan) {
            frm.add_custom_button(__("Initialize Production Stages"), () => run_order_method(frm, "initialize_production_stages"), __("Production"));
        }
        if (!frm.is_new()) {
            frm.add_custom_button(__("Factory Pieces"), () => frappe.set_route("List", "Factory Piece", {factory_order: frm.doc.name}), __("View"));
            frm.add_custom_button(__("Production Timeline"), () => frappe.set_route("factory-order-timeline", frm.doc.name), __("View"));
            frm.add_custom_button(__("Cutting Orders"), () => frappe.set_route("List", "Cutting Order", {factory_order: frm.doc.name}), __("View"));
        }
        if (!frm.is_new() && canFinance) {
            frm.add_custom_button(__("Factory Cost Ledger"), () => frappe.set_route("List", "Factory Cost Ledger", {factory_order: frm.doc.name}), __("Costing"));
            frm.add_custom_button(__("Recalculate Actual Cost"), () => recalculate_costing(frm), __("Costing"));
            frm.add_custom_button(__("Accounting Settings"), () => frappe.set_route("Form", "Factory Accounting Settings"), __("Costing"));
            frm.add_custom_button(__("Worker Cost Rates"), () => frappe.set_route("List", "Factory Worker Cost Rate"), __("Costing"));
            frm.add_custom_button(__("Workstation Cost Rates"), () => frappe.set_route("List", "Factory Workstation"), __("Costing"));
        }

        const stages = frm.doc.production_stages || [];
        const productionComplete = stages.length && stages.every(row => ["Completed", "Skipped"].includes(row.status));
        if (!frm.is_new() && canDeliver && productionComplete && !["Ready for Delivery", "Delivered", "Closed", "Cancelled"].includes(frm.doc.status)) {
            frm.add_custom_button(__("Mark Ready for Delivery"), () => run_delivery_action(frm, "mark_ready_for_delivery"), __("Delivery"));
        }
        if (!frm.is_new() && canDeliver && frm.doc.status === "Ready for Delivery") {
            frm.add_custom_button(__("Confirm Delivered"), () => run_delivery_action(frm, "mark_delivered"), __("Delivery"));
        }

        const active = stages.find(row => ["Ready", "In Progress", "Blocked"].includes(row.status));
        if (!active) return;
        if (["Ready", "Blocked"].includes(active.status) && canPlan) {
            frm.add_custom_button(__("Auto Assign Workstation: {0}", [active.stage]), () => run_stage_method(frm, "auto_assign_stage", active), __("Production"));
        }
        if (["Ready", "Blocked"].includes(active.status) && can_work_stage(active.stage)) {
            frm.add_custom_button(__("Start / Resume: {0}", [active.stage]), () => run_stage_method(frm, "start_stage", active), __("Production"));
        }
        if (active.status === "In Progress" && can_work_stage(active.stage)) {
            frm.add_custom_button(__("Complete: {0}", [active.stage]), () => run_stage_method(frm, "complete_stage", active), __("Production"));
            frm.add_custom_button(__("Block: {0}", [active.stage]), () => block_stage(frm, active), __("Production"));
        }
    },
});

frappe.ui.form.on("Factory Order Stage", {
    workstation(frm, cdt, cdn) {
        const row = locals[cdt][cdn];
        if (!row.workstation || !row.stage) return;
        frappe.db.get_value("Factory Workstation", row.workstation, ["stage", "status"]).then(r => {
            const workstation = r.message || {};
            if (workstation.stage && workstation.stage !== row.stage) {
                frappe.msgprint(__("This workstation belongs to {0}, not {1}", [workstation.stage, row.stage]));
                frappe.model.set_value(cdt, cdn, "workstation", null);
            } else if (workstation.status && workstation.status !== "Active") {
                frappe.msgprint(__("Selected workstation is not active"));
            }
        });
    },
});

function has_any_role(roles) { return roles.some(role => frappe.user.has_role(role)); }
function can_work_stage(stage) { return has_any_role(FACTORY_SUPERVISION_ROLES) || frappe.user.has_role(FACTORY_STAGE_ROLES[stage]); }
function run_order_method(frm, method) { frm.call(method).then(() => frm.reload_doc()); }
function run_delivery_action(frm, method) {
    frappe.call({method: `wood_factory.delivery.${method}`, args: {factory_order: frm.doc.name}, freeze: true}).then(r => {
        frappe.show_alert({message: __((r.message || {}).status || "Delivery status updated"), indicator: "green"});
        frm.reload_doc();
    });
}
function run_stage_method(frm, method, row) {
    frm.call(method, {row_name: row.name}).then(r => {
        const workstation = r.message && r.message.workstation;
        const costing = r.message && r.message.costing;
        let message;
        if (costing && Object.prototype.hasOwnProperty.call(costing, "labor_cost")) {
            message = __("Stage completed. Labor: {0}, Machine: {1}, Costing: {2}", [costing.labor_cost || 0, costing.machine_cost || 0, costing.status]);
        } else if (costing) {
            message = __("Stage completed. Costing status: {0}", [costing.status || "Pending"]);
        } else {
            message = workstation ? __("Assigned to {0}", [workstation]) : __("Production stage updated");
        }
        frappe.show_alert({message, indicator: costing && costing.status === "Partial" ? "orange" : "green"});
        frm.reload_doc();
    });
}
function recalculate_costing(frm) {
    frm.call("recalculate_actual_costing").then(r => {
        const totals = (r.message || {}).totals || {};
        frappe.show_alert({message: __("Actual cost recalculated: {0}", [totals.total_actual_cost || 0]), indicator: totals.costing_status === "Partial" ? "orange" : "green"});
        frm.reload_doc();
    });
}
function block_stage(frm, row) {
    frappe.prompt([{fieldname: "reason", fieldtype: "Small Text", label: __("Block Reason"), reqd: 1}], values => {
        frm.call("block_stage", {row_name: row.name, reason: values.reason}).then(() => frm.reload_doc());
    }, __("Block Production Stage"), __("Block"));
}
