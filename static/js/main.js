document.addEventListener('DOMContentLoaded', function() {
    // 手机端侧边抽屉菜单
    const mobileAvatarBtn = document.getElementById('mobileAvatarBtn');
    const mobileDrawer = document.getElementById('mobileDrawer');
    const drawerBackdrop = document.getElementById('drawerBackdrop');
    const closeDrawerBtn = document.getElementById('closeDrawerBtn');

    if (mobileAvatarBtn && mobileDrawer && drawerBackdrop) {
        function openDrawer() {
            mobileDrawer.classList.add('active');
            drawerBackdrop.classList.add('active');
            document.body.style.overflow = 'hidden'; // 阻止背景滚动
        }

        function closeDrawer() {
            mobileDrawer.classList.remove('active');
            drawerBackdrop.classList.remove('active');
            document.body.style.overflow = '';
        }

        mobileAvatarBtn.addEventListener('click', openDrawer);
        drawerBackdrop.addEventListener('click', closeDrawer);
        if (closeDrawerBtn) {
            closeDrawerBtn.addEventListener('click', closeDrawer);
        }
    }

    // 评论模态框或发帖模态框触发器
    // 主要是悬浮 + 按钮拉起 Bootstrap 发帖 modal
    const mobileFab = document.getElementById('mobileFab');
    if (mobileFab) {
        mobileFab.addEventListener('click', function() {
            const postModalEl = document.getElementById('postModal');
            if (postModalEl) {
                const postModal = new bootstrap.Modal(postModalEl);
                postModal.show();
            }
        });
    }

    // ==================== 发帖图片选择与本地预览逻辑 ====================
    // 初始化单个发帖表单的联动逻辑
    function initPostFormLogic(config) {
        const form = document.getElementById(config.formId);
        const textarea = document.getElementById(config.textareaId);
        const fileInput = document.getElementById(config.fileInputId);
        const mediaBtn = document.getElementById(config.mediaBtnId);
        const previewWrapper = document.getElementById(config.previewWrapperId);
        const previewGrid = document.getElementById(config.previewGridId);
        const clearBtn = document.getElementById(config.clearBtnId);
        const submitBtn = document.getElementById(config.submitBtnId);
        const maxFiles = config.maxFiles || 4;

        if (!form || !textarea || !fileInput || !submitBtn) return;

        // 辅助：根据文字和图片更新按钮状态
        function updateButton() {
            const hasText = textarea.value.trim().length > 0;
            const hasImage = fileInput.files && fileInput.files.length > 0;
            submitBtn.disabled = (!hasText && !hasImage);
        }

        // 1. 点击媒体图标触发文件选择
        if (mediaBtn) {
            mediaBtn.addEventListener('click', () => fileInput.click());
        }

        function selectedFiles() {
            return Array.from(fileInput.files || []);
        }

        function applyFileLimit() {
            const files = selectedFiles();
            if (files.length <= maxFiles) {
                return files;
            }

            const dataTransfer = new DataTransfer();
            files.slice(0, maxFiles).forEach(file => dataTransfer.items.add(file));
            fileInput.files = dataTransfer.files;
            return selectedFiles();
        }

        function renderPreview(files) {
            if (!previewGrid || !previewWrapper) return;

            previewGrid.innerHTML = '';
            previewGrid.className = `post-image-preview-grid post-image-preview-count-${files.length}`;

            files.forEach((file, index) => {
                const itemDiv = document.createElement('div');
                itemDiv.className = 'preview-image-item';

                const img = document.createElement('img');
                img.src = URL.createObjectURL(file);
                img.alt = file.name;
                img.onload = () => URL.revokeObjectURL(img.src);
                itemDiv.appendChild(img);

                // 创建单独的 X 删除按钮
                const deleteBtn = document.createElement('button');
                deleteBtn.type = 'button';
                deleteBtn.className = 'preview-image-delete-btn';
                deleteBtn.innerHTML = '<i class="bi bi-x fs-6"></i>';
                
                // 绑定点击事件排除对应的文件
                deleteBtn.addEventListener('click', function(e) {
                    e.preventDefault();
                    e.stopPropagation();
                    removeSingleFile(index);
                });

                itemDiv.appendChild(deleteBtn);
                previewGrid.appendChild(itemDiv);
            });

            previewWrapper.classList.toggle('d-none', files.length === 0);
        }

        // 精准移出被删去的文件
        function removeSingleFile(indexToRemove) {
            const currentFiles = selectedFiles();
            const dataTransfer = new DataTransfer();

            currentFiles.forEach((file, idx) => {
                if (idx !== indexToRemove) {
                    dataTransfer.items.add(file);
                }
            });

            fileInput.files = dataTransfer.files;
            
            // 刷新
            const updatedFiles = selectedFiles();
            renderPreview(updatedFiles);
            updateButton();
        }

        // 2. 选择文件后的本地读取预览
        fileInput.addEventListener('change', function() {
            const files = applyFileLimit();
            renderPreview(files);
            updateButton();
        });

        // 3. 清除选中图片
        function clearImages() {
            fileInput.value = '';
            if (previewWrapper) {
                previewWrapper.classList.add('d-none');
            }
            if (previewGrid) {
                previewGrid.innerHTML = '';
                previewGrid.className = 'post-image-preview-grid';
            }
            updateButton();
        }

        if (clearBtn) {
            clearBtn.addEventListener('click', clearImages);
        }

        // 4. 输入文字的监听
        textarea.addEventListener('input', updateButton);

        // 初始状态计算
        updateButton();
    }

    // 运行 PC 端发帖联动
    initPostFormLogic({
        formId: 'pc-post-form',
        textareaId: 'pc-post-textarea',
        fileInputId: 'pc-post-image-input',
        mediaBtnId: 'pc-media-btn',
        previewWrapperId: 'pc-image-preview-wrapper',
        previewGridId: 'pc-image-preview-grid',
        clearBtnId: null,
        submitBtnId: 'pc-post-submit',
        maxFiles: 4
    });

    // 运行 Modal 弹窗发帖联动
    initPostFormLogic({
        formId: 'modal-post-form',
        textareaId: 'modal-post-textarea',
        fileInputId: 'modal-post-image',
        mediaBtnId: null, // label for 属性已绑定触发 file select，无需 JS 点击
        previewWrapperId: 'modal-image-preview-wrapper',
        previewGridId: 'modal-image-preview-grid',
        clearBtnId: null,
        submitBtnId: 'modal-post-submit',
        maxFiles: 4
    });

    // ==================== 全屏大图 Lightbox 灯箱逻辑 ====================
    const lightbox = document.getElementById('globalLightbox');
    const lightboxImg = document.getElementById('lightboxImage');

    if (lightbox && lightboxImg) {
        // 打开灯箱
        window.openLightbox = function(src) {
            lightboxImg.src = src;
            lightbox.classList.remove('d-none');
            document.body.style.overflow = 'hidden'; // 锁定网页滚动
            
            // 延迟以启动 CSS opacity/scale 动画
            setTimeout(() => {
                lightbox.classList.add('active');
            }, 10);
        };

        // 关闭灯箱
        window.closeLightbox = function() {
            lightbox.classList.remove('active');
            
            // 动画结束后隐藏 DOM
            setTimeout(() => {
                lightbox.classList.add('d-none');
                lightboxImg.src = '';
                document.body.style.overflow = ''; // 还原滚动
            }, 250);
        };

        // 1. 使用高效的【事件委托】机制监听 timeline 或 profile 卡片里的图片点击
        document.body.addEventListener('click', function(e) {
            // 只有当点击图片且它属于 post-card-media 组件时触发
            if (e.target.tagName === 'IMG' && e.target.closest('.post-card-media')) {
                e.preventDefault();
                window.openLightbox(e.target.src);
            }
        });

        // 2. 支持 Esc 键关闭
        document.addEventListener('keydown', function(e) {
            if (e.key === 'Escape' && !lightbox.classList.contains('d-none')) {
                window.closeLightbox();
            }
        });
    }

    // ==================== Post Card Click Delegation ====================
    document.body.addEventListener('click', function(e) {
        const card = e.target.closest('.post-card');
        if (!card) return;

        // 隔离可交互元素：如果点击了 a、button、form、input、textarea、select、dropdown 或者是 lightbox 本身或分享操作，不跳转
        if (e.target.closest('a, button, form, input, textarea, select, .dropdown, [data-bs-toggle], .post-action, .lightbox-overlay')) {
            return;
        }

        const url = card.getAttribute('data-post-url');
        if (url) {
            window.location.href = url;
        }
    });

    // Social actions submit their existing POST forms without navigating away.
    function socialActionPath(form) {
        const path = new URL(form.action, window.location.origin).pathname;
        if (/^\/posts\/\d+\/(like|comment|repost|delete)$/.test(path)) return path;
        if (/^\/users\/\d+\/(follow|unfollow)$/.test(path)) return path;
        return null;
    }

    function actionFeedback(form, message) {
        let feedback = form.querySelector('.action-feedback');
        if (!feedback) {
            feedback = document.createElement('span');
            feedback.className = 'action-feedback';
            form.appendChild(feedback);
        }
        feedback.textContent = message;
        window.setTimeout(() => feedback.remove(), 2600);
    }

    function formsForPath(path) {
        return Array.from(document.querySelectorAll('form')).filter(function(form) {
            return new URL(form.action, window.location.origin).pathname === path;
        });
    }

    function updatePostAction(postId, action, active, count) {
        const path = `/posts/${postId}/${action}`;
        formsForPath(path).forEach(function(form) {
            const button = form.querySelector('button');
            if (!button) return;

            if (action === 'like') {
                button.classList.toggle('liked', active);
                button.setAttribute('aria-label', active ? 'Unlike post' : 'Like post');
                const icon = button.querySelector('i');
                if (icon) icon.className = active ? 'bi bi-heart-fill' : 'bi bi-heart';
            }
            if (action === 'repost') {
                button.classList.toggle('reposted', active);
            }

            const countElement = button.querySelector('.like-count, .repost-count, span');
            if (countElement) countElement.textContent = count;
        });
    }

    function updateReplyCount(postId, count) {
        document.querySelectorAll(`[data-post-id="${postId}"]`).forEach(function(card) {
            const selector = card.classList.contains('reply-post')
                ? '.reply-post-main .reply-post-actions .action-comment span'
                : card.classList.contains('post-detail-card')
                    ? '.post-detail-actions .action-comment span'
                    : '.post-card-footer .action-comment span';
            const countElement = card.querySelector(selector);
            if (countElement) countElement.textContent = count;
        });
    }

    function appendReply(form, payload) {
        if (!payload.reply_html) return;

        const parentCard = document.querySelector(`[data-post-id="${payload.parent_post_id}"]`);
        let container = null;

        if (parentCard && parentCard.classList.contains('reply-post')) {
            container = parentCard.querySelector(':scope > .reply-post-children');
            if (!container) {
                container = document.createElement('div');
                container.className = 'reply-post-children';
                parentCard.appendChild(container);
            }
        } else if (parentCard && parentCard.classList.contains('post-detail-card')) {
            container = document.querySelector('.post-replies-section');
        }

        if (!container) container = form.closest('.post-comments');
        if (container) container.insertAdjacentHTML('beforeend', payload.reply_html);
    }

    function updateFollowAction(userId, following) {
        Array.from(document.querySelectorAll('form')).forEach(function(form) {
            const path = new URL(form.action, window.location.origin).pathname;
            if (!new RegExp(`^/users/${userId}/(follow|unfollow)$`).test(path)) return;

            form.action = form.action.replace(/\/(follow|unfollow)$/, following ? '/unfollow' : '/follow');
            const button = form.querySelector('button');
            if (!button) return;
            button.classList.toggle('btn-following', following);
            button.classList.toggle('btn-follow', !following);
            const label = button.querySelector('.btn-following-text');
            if (label) label.textContent = following ? 'Following' : 'Follow';
            else button.textContent = following ? 'Following' : 'Follow';
        });
    }

    document.body.addEventListener('submit', async function(event) {
        const form = event.target;
        if (!(form instanceof HTMLFormElement)) return;

        const path = socialActionPath(form);
        if (!path) return;

        event.preventDefault();
        const submitButton = event.submitter || form.querySelector('button[type="submit"], button');
        if (submitButton) submitButton.disabled = true;

        try {
            const response = await fetch(form.action, {
                method: 'POST',
                body: new FormData(form),
                credentials: 'same-origin',
                headers: { 'X-Requested-With': 'XMLHttpRequest', 'Accept': 'application/json' },
            });
            const payload = await response.json();
            if (!response.ok || !payload.ok) {
                actionFeedback(form, payload.message || 'Action could not be completed.');
                return;
            }

            if (payload.action === 'like') {
                updatePostAction(payload.post_id, 'like', payload.liked, payload.like_count);
            } else if (payload.action === 'repost') {
                updatePostAction(payload.post_id, 'repost', payload.reposted, payload.repost_count);
            } else if (payload.action === 'reply') {
                form.reset();
                updateReplyCount(payload.parent_post_id, payload.reply_count);
                appendReply(form, payload);
            } else if (payload.action === 'follow') {
                updateFollowAction(payload.user_id, payload.following);
            } else if (payload.action === 'delete') {
                const card = form.closest('.reply-post, .post-card, .post-detail-card');
                if (card) card.remove();
            }
        } catch (error) {
            actionFeedback(form, 'Network error. Please try again.');
        } finally {
            if (submitButton) submitButton.disabled = false;
        }
    });
});
