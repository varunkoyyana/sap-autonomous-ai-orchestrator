sap.ui.define([
  "sap/ui/core/mvc/Controller",
  "sap/ui/model/json/JSONModel",
  "sap/m/MessageToast",
  "sap/m/Dialog",
  "sap/m/Button",
  "sap/m/Text",
  "sap/m/VBox",
  "sap/m/HBox",
  "sap/m/Label",
  "sap/m/Input"
], function(Controller, JSONModel, MessageToast, Dialog, Button, Text, VBox, HBox, Label, Input) {
  "use strict";
console.log("Main.controller.js loaded!");
  // Sample recommended questions by domain
  const promptMap = {
    hr: [
      { question: "Tell me about leave policy in the company" },
      { question: "How do I submit a leave request?" },
      { question: "I want to apply for leave" },
      { question: "Help me apply for leave" }
    ],
    procurement: [
      { question: "What is the procurement process?" },
      { question: "How to order new laptops?" },
      { question: "I want to place an order" }
    ],
    finance: [
      { question: "Show me the latest invoice status" },
      { question: "How to claim expenses?" },
      { question: "I need to process an invoice" }
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
        recommended: promptMap["hr"],
        conversation: [],
        isLoading: false,
        showUploadArea: false,
        uploadProgress: 0,
        extractedData: null,
        showConfirmation: false
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
      
      if (!sTask.trim()) {
        MessageToast.show("Please enter a question");
        return;
      }

      this._addMessage("user", sTask);
      this._setLoading(true);
      
      var that = this;

      $.ajax({
        url: "https://orchestrator-responsive-jaguar-ct.cfapps.us10-001.hana.ondemand.com/workflow",
        method: "POST",
        contentType: "application/json",
        data: JSON.stringify({ domain: sDomain, task: sTask }),
        success: function(data) {
          that._setLoading(false);
          that._handleAgentResponse(data);
          that.getView().byId("taskInput").setValue("");
        },
        error: function(xhr) {
          that._setLoading(false);
          that._addMessage("error", "Error: " + xhr.status + " " + xhr.statusText);
        }
      });
    },

    _handleAgentResponse: function(data) {
      // Add the main response message
      this._addMessage("agent", data.result || "No response received");
      
      // Check if the response mentions form download
      var resultText = data.result || "";
      var isFormResponse = resultText.toLowerCase().includes("download") && 
                          resultText.toLowerCase().includes("form");
      
      if (isFormResponse) {
        var oModel = this.getView().getModel();
        
        var downloadMessage = {
          type: "form_download", 
          content: "📋 Leave Request Form is ready for download",
          download_url: "/download/leave_request_form",
          form_name: "Leave Request Form",
          instructions: [
            "1. Click the download button to get the form",
            "2. Fill out all required fields", 
            "3. Save the completed form",
            "4. Use the upload button to submit it"
          ],
          timestamp: new Date().toLocaleTimeString()
        };
        
        var conversation = oModel.getProperty("/conversation");
        conversation.push(downloadMessage);
        oModel.setProperty("/conversation", conversation);
        
        // Show upload area
        oModel.setProperty("/showUploadArea", true);
        
        MessageToast.show("Form ready for download!");
      }
      
      // Check if this is a document processing response with extracted data
      if (data.extracted_data) {
        this._handleExtractedData(data);
      }
      
      // Show any additional information
      if (data.source_document) {
        this._addMessage("info", "Source: " + data.source_document);
      }
    },

    _handleExtractedData: function(response) {
      var oModel = this.getView().getModel();
      
      try {
        var extractedData = typeof response.extracted_data === 'string' 
          ? JSON.parse(response.extracted_data) 
          : response.extracted_data;
        
        oModel.setProperty("/extractedData", extractedData);
        oModel.setProperty("/showConfirmation", true);
        
        this._showConfirmationDialog(extractedData, response);
      } catch (e) {
        MessageToast.show("Error parsing extracted data");
      }
    },

    _showConfirmationDialog: function(extractedData, response) {
      var that = this;
      
      if (!this._confirmationDialog) {
        this._confirmationDialog = new Dialog({
          title: "Confirm Extracted Information",
          contentWidth: "600px",
          contentHeight: "500px",
          verticalScrolling: true,
          beginButton: new Button({
            text: "Submit",
            type: "Emphasized",
            press: function() {
              that._submitToSAP(extractedData);
              that._confirmationDialog.close();
            }
          }),
          endButton: new Button({
            text: "Cancel",
            press: function() {
              that._confirmationDialog.close();
            }
          })
        });
        this.getView().addDependent(this._confirmationDialog);
      }
      
      // Create content for the dialog
      var oVBox = new VBox({
        items: [
          new Text({
            text: "Please review and confirm the extracted information:",
            class: "sapUiMediumMarginBottom"
          })
        ]
      });
      
      // Add extracted data fields
      Object.keys(extractedData).forEach(function(key) {
        if (extractedData[key] && extractedData[key] !== "null") {
          oVBox.addItem(new HBox({
            items: [
              new Label({
                text: key.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase()) + ":",
                class: "sapUiTinyMarginEnd"
              }),
              new Input({
                value: extractedData[key],
                editable: true,
                change: function(oEvent) {
                  extractedData[key] = oEvent.getSource().getValue();
                }
              })
            ],
            class: "sapUiTinyMarginBottom"
          }));
        }
      });
      
      this._confirmationDialog.removeAllContent();
      this._confirmationDialog.addContent(oVBox);
      this._confirmationDialog.open();
    },

    _submitToSAP: function(extractedData) {
    var that = this;
    // Show busy indicator, if desired
    sap.ui.core.BusyIndicator.show();
    jQuery.ajax({
        url: "https://hr-agent-fearless-gorilla-qc.cfapps.us10-001.hana.ondemand.com/submit_leave_to_iflow",
        method: "POST",
        contentType: "application/json",
        data: JSON.stringify(extractedData),
        success: function(response) {
            sap.ui.core.BusyIndicator.hide();
            if (response.sap_status_code === 200) {
                sap.m.MessageToast.show("Leave request submitted to HR_iflow!");
            } else {
                sap.m.MessageBox.error("SAP iFlow error: " + JSON.stringify(response.sap_response));
            }
        },
        error: function(xhr, status, error) {
            sap.ui.core.BusyIndicator.hide();
            sap.m.MessageBox.error("Failed to send request to HR_iflow: " + error);
        }
    });
},

    onDownloadForm: function(oEvent) {
      var downloadUrl = oEvent.getSource().data("downloadUrl");
      var fullUrl = "https://hr-agent-fearless-gorilla-qc.cfapps.us10-001.hana.ondemand.com" + downloadUrl;
      
      window.open(fullUrl, '_blank');
      MessageToast.show("Form download started");
    },

    onFileUploadPress: function() {
      // Create file input programmatically
      var fileInput = document.createElement('input');
      fileInput.type = 'file';
      fileInput.accept = '.pdf,.doc,.docx,.txt,.md';
      fileInput.onchange = (event) => {
        var files = event.target.files;
        if (files && files.length > 0) {
          this._uploadFile(files[0]);
        }
      };
      fileInput.click();
    },

    _uploadFile: function(file) {
      var that = this;
      var oModel = this.getView().getModel();
      
      // Validate file type
      var allowedTypes = ['.pdf', '.doc', '.docx', '.txt', '.md'];
      var fileExtension = '.' + file.name.split('.').pop().toLowerCase();
      
      if (!allowedTypes.includes(fileExtension)) {
        MessageToast.show("File type not supported. Please upload: " + allowedTypes.join(', '));
        return;
      }
      
      // Show upload progress
      oModel.setProperty("/uploadProgress", 0);
      this._addMessage("info", "📤 Uploading " + file.name + "...");
      
      var formData = new FormData();
      formData.append('file', file);
      
      var xhr = new XMLHttpRequest();
      
      xhr.upload.addEventListener('progress', function(e) {
        if (e.lengthComputable) {
          var progress = Math.round((e.loaded / e.total) * 100);
          oModel.setProperty("/uploadProgress", progress);
        }
      });
      
      xhr.addEventListener('load', function() {
        if (xhr.status === 200) {
          var response = JSON.parse(xhr.responseText);
          that._addMessage("success", "✅ File uploaded successfully!");
          that._handleAgentResponse(response);
        } else {
          that._addMessage("error", "❌ Upload failed: " + xhr.statusText);
        }
        oModel.setProperty("/uploadProgress", 0);
      });
      
      xhr.addEventListener('error', function() {
        that._addMessage("error", "❌ Upload failed: Network error");
        oModel.setProperty("/uploadProgress", 0);
      });
      
      xhr.open('POST', 'https://hr-agent-fearless-gorilla-qc.cfapps.us10-001.hana.ondemand.com/upload/leave_document');
      xhr.send(formData);
    },

    _addMessage: function(type, content) {
      var oModel = this.getView().getModel();
      var conversation = oModel.getProperty("/conversation") || [];
      
      conversation.push({
        type: type,
        content: content,
        timestamp: new Date().toLocaleTimeString()
      });
      
      oModel.setProperty("/conversation", conversation);
      
      // Scroll to bottom
      setTimeout(function() {
        var chatContainer = document.querySelector("#chatContainer");
        if (chatContainer) {
          chatContainer.scrollTop = chatContainer.scrollHeight;
        }
      }, 100);
    },

    _setLoading: function(isLoading) {
      this.getView().getModel().setProperty("/isLoading", isLoading);
    },

    // Formatters for the view
    formatMessageClass: function(type) {
      switch(type) {
        case "user": return "userMessage";
        case "agent": return "agentMessage";
        case "error": return "errorMessage";
        case "success": return "successMessage";
        case "info": return "infoMessage";
        case "form_download": return "formDownloadMessage";
        default: return "defaultMessage";
      }
    },

    formatMessageIcon: function(type) {
      switch(type) {
        case "user": return "sap-icon://person-placeholder";
        case "agent": return "sap-icon://robot";
        case "error": return "sap-icon://error";
        case "success": return "sap-icon://accept";
        case "info": return "sap-icon://information";
        case "form_download": return "sap-icon://download";
        default: return "sap-icon://message-information";
      }
    }
  });
});