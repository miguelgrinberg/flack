'use strict';
var app = app || {};

// MessageView handles a rendering of a single message.
app.MessageView = Backbone.View.extend({
    tagName: 'div',
    template: _.template($('#message-template').html()),

    initialize: function(options) {
        _.bindAll(this, 'render');

        // The model for this view is a Message instance.
        this.model.bind('change', this.render);
    },

    render: function() {
        // Render the message to the page.
        this.$el.html(this.template({msg: this.model.toJSON()}));

        // Render the user in the appropriate part of the message.
        var user = app.userList.get(this.model.get('user_id'));
        if (user) {
            var userView = new app.UserView({
                tagName: 'span',
                model: user,
                showOffline: true
            });
            this.$el.find('.user').append(userView.render().el);
        }
        return this;
    }
});
