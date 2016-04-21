'use strict';

var app = app || {};

$(function() {
    // Create the models.
    app.userList = new app.UserList();
    app.messageList = new app.MessageList();
    app.token = new app.Token();

    // Create the views.
    app.userListView = new app.UserListView({collection: app.userList});
    app.messageListView = new app.MessageListView({collection: app.messageList});
    app.loginFormView = new app.LoginFormView({model: app.token});
    app.postFormView = new app.PostFormView({model: app.token});
    app.statsView = new app.StatsView();

    // Set up auto-refresh for the user and message lists.
    app.userListView.refresh(function() {
        app.messageListView.refresh(function() {
            window.setInterval(function() {
                app.userListView.refresh();
            }, 1000);
            window.setInterval(function() {
                app.messageListView.refresh();
            }, 1000);
        });
    });

    // Render the form views.
    app.loginFormView.render();
    app.postFormView.render();
    $('form[data-submit!=""]').submit(function(ev) {
        var form = $(ev.currentTarget);
        var target = app[form.data('submit')];
        var values = {};
        for (var i = 0; i < form.children().length; i++) {
            var control = form.children().eq(i);
            var name = control.attr('name') || control.attr('id');
            if (name) {
                values[name] = control.val();
                control.val('');
            }
        }
        target.trigger('submit', values);
        return false;
    });

    // Render the stats view
    app.statsView.render();

    // Auto-refresh stats view
    window.setInterval(function() {
        app.statsView.render();
    }, 5000);

    // Set up authentication in Backbone.sync
    var _sync = Backbone.sync
    Backbone.sync = function(method, model, options) {
        var token = app.token.get('token');
        if (token) {
            // If we have a token, then we have to use it, even for freely
            // accessible endpoints, as this is what indirectly informs the
            // server that the user is online.
            options.headers = options.headers || {};
            _.extend(options.headers, {'Authorization': 'Bearer ' + token})
        }
        var error_callback = options.error;
        options.error = function(xhr) {
            if (error_callback) {
                error_callback.apply(this, xhr);
            }
            if (xhr.status == 401) {
                // Token became invalid, so we have to log user out
                app.token.set('token', null);
            }
        }
        return _sync.call(this, method, model, options);
    }
});
