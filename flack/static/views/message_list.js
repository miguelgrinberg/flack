'use strict';
var app = app || {};

// MessageListView handles the message list portion of the page.
app.MessageListView = Backbone.View.extend({
    el: '#messages',
    updated_since: 0,

    initialize: function(options) {
        _.bindAll(this, 'updateMessage', 'render', 'refresh');

        // Keep a reference to the message collection.
        this.collection = options.collection;
    },

    updateMessage: function(msg) {
        // First we need to know if the message pane is scrolled all the way
        // to the bottom, because in that case we want to keep it scrolled
        // after the message is added or updated.
        var scrollToBottom = this.$el.prop('scrollHeight') -
            this.$el.prop('clientHeight') <= this.$el.prop('scrollTop');

        // If the message is already known, we just need to update it.
        // This will cause it to update also on the page.
        if (this.collection.get(msg.get('id'))) {
            this.collection.add(msg, {merge: true});
            return;
        }

        // If the message is new, then add it to the collection and render it.
        // Note the use of a sub-view
        this.collection.add(msg);
        var msgView = new app.MessageView({model: msg});
        this.$el.append(msgView.render().el);

        // If necessary, scroll the message list to the bottom.
        if (scrollToBottom) {
            this.$el.scrollTop(this.$el.prop('scrollHeight') -
                this.$el.prop('clientHeight'));
        }
    },

    render: function(updates) {
        // Update the list of message models one by one.
        updates = updates || this.collection;
        updates.forEach(function(msg) {
            this.updateMessage(msg);
        }, this);
    },

    refresh: function(cb) {
        // Obtain list of message updates from the server.
        var msgs = new app.MessageList();
        msgs.fetch({
            data: {updated_since: this.updated_since},
            success: function() {
                // Render the new or updated messages.
                this.render(msgs);
                if (msgs.length > 0) {
                    this.updated_since =
                        msgs.at(msgs.length - 1).get('updated_at');
                }
                if (cb)
                    cb();
            }.bind(this),
        });
    },
});
