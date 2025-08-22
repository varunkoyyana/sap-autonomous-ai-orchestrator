sap.ui.define([
  "sap/ui/core/mvc/Controller",
  "sap/ui/model/json/JSONModel"
], function(Controller, JSONModel) {
  "use strict";

  // Sample recommended questions by domain
  const promptMap = {
    hr: [
      { question: "Tell me about leave policy in the company" },
      { question: "How do I submit a leave request?" }
    ],
    procurement: [
      { question: "What is the procurement process?" },
      { question: "How to order new laptops?" }
    ],
    finance: [
      { question: "Show me the latest invoice status" },
      { question: "How to claim expenses?" }
    ]
  };

  return Controller.extend("sap.ai.orchestrator.controller.Main", {
    onInit: function() {
      var oModel = new JSONModel({
        domains: [
          { key: "hr", text: "HR" },
          { key: "finance", text: "Finance" },
          { key: "procurement", text: "Procurement" }
        ],
        recommended: promptMap["hr"]
      });
      this.getView().setModel(oModel);
    },

    onDomainChange: function(oEvent) {
      var key = oEvent.getSource().getSelectedKey();
      this.getView().getModel().setProperty("/recommended", promptMap[key]);
    },

    onRecommendedPress: function(oEvent) {
      var question = oEvent.getSource().getTitle();
      this.getView().byId("taskInput").setValue(question);
    },

    onSubmit: function() {
      var sDomain = this.getView().byId("domainSelect").getSelectedKey();
      var sTask = this.getView().byId("taskInput").getValue();
      var oView = this.getView();
      $.ajax({
        url: "https://orchestrator-responsive-jaguar-ct.cfapps.us10-001.hana.ondemand.com/workflow",
        method: "POST",
        contentType: "application/json",
        data: JSON.stringify({ domain: sDomain, task: sTask }),
        success: function(data) {
          oView.byId("result").setText(data.result || JSON.stringify(data));
        },
        error: function(xhr) {
          oView.byId("result").setText("Error: " + xhr.status + " " + xhr.statusText + "\n" + xhr.responseText);
        }
      });
    }
  });
});
